import asyncpg
import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


def _pg_config() -> dict:
    return {
        'host':     os.getenv('PG_HOST', 'localhost'),
        'port':     int(os.getenv('PG_PORT', '5432')),
        'database': os.getenv('PG_DB', ''),
        'user':     os.getenv('PG_USER', ''),
        'password': os.getenv('PG_PASSWORD', ''),
    }


class DatabaseManager:
    def __init__(self):
        self._pool: Optional[asyncpg.Pool] = None
        self._lock = asyncio.Lock()

    async def initialize(self):
        cfg = _pg_config()
        if not cfg['database'] or not cfg['user']:
            raise ValueError("PG_DB et PG_USER doivent être définis")
        self._pool = await asyncpg.create_pool(**cfg, min_size=2, max_size=10)
        logger.info("Pool PostgreSQL initialisé")

    async def close(self):
        if self._pool:
            await self._pool.close()

    @asynccontextmanager
    async def get_connection(self):
        if not self._pool:
            async with self._lock:
                if not self._pool:
                    await self.initialize()
        conn = await self._pool.acquire()
        try:
            yield conn
        except Exception:
            raise
        finally:
            await self._pool.release(conn)

    async def fetch(self, query: str, *args) -> List[Dict[str, Any]]:
        async with self.get_connection() as conn:
            rows = await conn.fetch(query, *args)
            return [dict(r) for r in rows]

    async def fetchrow(self, query: str, *args) -> Optional[Dict[str, Any]]:
        async with self.get_connection() as conn:
            row = await conn.fetchrow(query, *args)
            return dict(row) if row else None

    async def fetchval(self, query: str, *args):
        async with self.get_connection() as conn:
            return await conn.fetchval(query, *args)

    async def execute(self, query: str, *args) -> str:
        async with self.get_connection() as conn:
            return await conn.execute(query, *args)

    async def executemany(self, query: str, params: list):
        async with self.get_connection() as conn:
            await conn.executemany(query, params)


class VoiceDataManager:
    def __init__(self, db: DatabaseManager):
        self.db = db

    async def get_user(self, user_id: int) -> Optional[Dict]:
        return await self.db.fetchrow(
            "SELECT * FROM user_voice_data WHERE user_id = $1", user_id
        )

    async def sync_member(self, user_id: int, username: str, nickname: str = None, avatar: str = None):
        await self.db.execute("""
            INSERT INTO user_voice_data (user_id, username, nickname, discord_avatar, last_seen)
            VALUES ($1, $2, $3, $4, NOW())
            ON CONFLICT (user_id) DO UPDATE
              SET username = EXCLUDED.username,
                  nickname = EXCLUDED.nickname,
                  discord_avatar = COALESCE(EXCLUDED.discord_avatar, user_voice_data.discord_avatar),
                  last_seen = NOW(),
                  updated_at = NOW()
        """, user_id, username, nickname, avatar)

    async def update_voice_time(self, user_id: int, username: str, seconds: int):
        await self.db.execute("""
            INSERT INTO user_voice_data (user_id, username, total_time, last_seen)
            VALUES ($1, $2, $3, NOW())
            ON CONFLICT (user_id) DO UPDATE
              SET total_time = user_voice_data.total_time + EXCLUDED.total_time,
                  username   = EXCLUDED.username,
                  last_seen  = NOW(),
                  updated_at = NOW()
        """, user_id, username, seconds)

    async def get_leaderboard(self, limit: int = 10) -> List[Dict]:
        return await self.db.fetch(
            "SELECT * FROM user_voice_data ORDER BY total_time DESC LIMIT $1", limit
        )

    async def find_by_name(self, term: str) -> Optional[Dict]:
        t = term.strip().lower()
        return await self.db.fetchrow("""
            SELECT * FROM user_voice_data
            WHERE LOWER(username) = $1 OR LOWER(nickname) = $1
               OR LOWER(username) LIKE $2 OR LOWER(nickname) LIKE $2
            ORDER BY CASE
                WHEN LOWER(username) = $1 THEN 1
                WHEN LOWER(nickname) = $1 THEN 2
                ELSE 3
            END LIMIT 1
        """, t, f"{t}%")


class WarnManager:
    def __init__(self, db: DatabaseManager):
        self.db = db

    async def add_warn(self, user_id: int, reason: str, moderator_id: int) -> bool:
        try:
            await self.db.execute("""
                INSERT INTO user_voice_data (user_id, username)
                VALUES ($1, $2) ON CONFLICT (user_id) DO NOTHING
            """, user_id, f"User_{user_id}")
            ts = int(datetime.now(timezone.utc).timestamp())
            await self.db.execute(
                "INSERT INTO warn (user_id, reason, create_time, moderator_id) VALUES ($1, $2, $3, $4)",
                user_id, reason, ts, moderator_id
            )
            return True
        except Exception as e:
            logger.error(f"add_warn error: {e}")
            return False

    async def get_user_warns(self, user_id: int) -> List[Dict]:
        return await self.db.fetch(
            "SELECT * FROM warn WHERE user_id = $1 ORDER BY create_time DESC", user_id
        )

    async def get_warn_count(self, user_id: int) -> int:
        return await self.db.fetchval(
            "SELECT COUNT(*) FROM warn WHERE user_id = $1", user_id
        ) or 0

    async def get_by_id(self, warn_id: int) -> Optional[Dict]:
        return await self.db.fetchrow("SELECT * FROM warn WHERE id = $1", warn_id)

    async def delete_warn(self, warn_id: int) -> bool:
        try:
            await self.db.execute("DELETE FROM warn WHERE id = $1", warn_id)
            return True
        except Exception:
            return False

    async def update_reason(self, warn_id: int, reason: str) -> bool:
        try:
            await self.db.execute("UPDATE warn SET reason = $1 WHERE id = $2", reason, warn_id)
            return True
        except Exception:
            return False

    async def delete_many(self, warn_ids: List[int]) -> int:
        if not warn_ids:
            return 0
        placeholders = ','.join(f'${i+1}' for i in range(len(warn_ids)))
        await self.db.execute(f"DELETE FROM warn WHERE id IN ({placeholders})", *warn_ids)
        return len(warn_ids)


class MessageStatsManager:
    def __init__(self, db: DatabaseManager):
        self.db = db

    async def increment(self, user_id: int, channel_id: int):
        await self.db.execute("""
            INSERT INTO user_voice_data (user_id, username)
            VALUES ($1, $2) ON CONFLICT (user_id) DO NOTHING
        """, user_id, f"User_{user_id}")
        await self.db.execute("""
            INSERT INTO user_message_stats (user_id, channel_id, message_count)
            VALUES ($1, $2, 1)
            ON CONFLICT (user_id, channel_id)
            DO UPDATE SET message_count = user_message_stats.message_count + 1,
                          updated_at = NOW()
        """, user_id, channel_id)

    async def get_total(self, user_id: int) -> int:
        return await self.db.fetchval(
            "SELECT COALESCE(SUM(message_count), 0) FROM user_message_stats WHERE user_id = $1",
            user_id
        ) or 0

    async def get_leaderboard(self, limit: int = 10) -> List[Dict]:
        return await self.db.fetch("""
            SELECT u.user_id, u.username, u.discord_avatar,
                   SUM(s.message_count) AS total_messages
            FROM user_voice_data u
            JOIN user_message_stats s ON u.user_id = s.user_id
            GROUP BY u.user_id, u.username, u.discord_avatar
            ORDER BY total_messages DESC
            LIMIT $1
        """, limit)


# ── Singletons ────────────────────────────────────────────────────────────────
db_manager           = DatabaseManager()
voice_manager        = VoiceDataManager(db_manager)
warn_manager         = WarnManager(db_manager)
message_stats_manager = MessageStatsManager(db_manager)


async def init_database():
    await db_manager.initialize()
    async with db_manager.get_connection() as conn:
        # Tables created by init.sql — just ensure command_status exists
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS command_status (
                id           SERIAL PRIMARY KEY,
                command_name VARCHAR(100) NOT NULL,
                guild_id     BIGINT,
                is_enabled   BOOLEAN DEFAULT TRUE,
                created_at   TIMESTAMPTZ DEFAULT NOW(),
                updated_at   TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE(command_name, guild_id)
            )
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_command_status_name_guild
            ON command_status(command_name, guild_id)
        """)
    logger.info("Base de données prête")
