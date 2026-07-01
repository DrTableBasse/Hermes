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
            INSERT INTO user_voice_data (user_id, username, nickname, discord_avatar, is_member, last_seen)
            VALUES ($1, $2, $3, $4, TRUE, NOW())
            ON CONFLICT (user_id) DO UPDATE
              SET username       = EXCLUDED.username,
                  nickname       = EXCLUDED.nickname,
                  discord_avatar = COALESCE(EXCLUDED.discord_avatar, user_voice_data.discord_avatar),
                  is_member      = TRUE,
                  last_seen      = NOW(),
                  updated_at     = NOW()
        """, user_id, username, nickname, avatar)

    async def mark_left(self, user_id: int):
        await self.db.execute(
            "UPDATE user_voice_data SET is_member = FALSE, updated_at = NOW() WHERE user_id = $1",
            user_id
        )

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


class XPManager:
    def __init__(self, db: DatabaseManager):
        self.db = db

    # XP par action
    XP_MESSAGE = 10
    XP_VOICE_PER_MINUTE = 1
    XP_ARTICLE = 50
    XP_BUMP = 5

    # Niveaux quadratiques : atteindre niveau N+1 coûte N²×100 XP
    # ex: niveau 10 → 10 000 XP, niveau 50 → 250 000 XP, niveau 100 → 1 000 000 XP
    @staticmethod
    def xp_for_level(level: int) -> int:
        return level * level * 100

    @staticmethod
    def level_from_xp(total_xp: int) -> int:
        if total_xp <= 0:
            return 1
        return max(1, int((total_xp / 100) ** 0.5))

    async def add_xp(self, user_id: int, amount: int) -> dict:
        """Add XP to user, return {new_xp, new_level, leveled_up}."""
        await self.db.execute("""
            INSERT INTO user_xp (user_id) VALUES ($1)
            ON CONFLICT (user_id) DO NOTHING
        """, user_id)

        row = await self.db.fetchrow("SELECT * FROM user_xp WHERE user_id = $1", user_id)
        old_level = row['current_level'] if row else 1

        await self.db.execute("""
            UPDATE user_xp
            SET total_xp = total_xp + $2,
                weekly_xp = weekly_xp + $2,
                monthly_xp = monthly_xp + $2
            WHERE user_id = $1
        """, user_id, amount)

        new_row = await self.db.fetchrow("SELECT total_xp FROM user_xp WHERE user_id = $1", user_id)
        new_xp = new_row['total_xp'] if new_row else 0
        new_level = self.level_from_xp(new_xp)

        if new_level != old_level:
            await self.db.execute(
                "UPDATE user_xp SET current_level = $2 WHERE user_id = $1",
                user_id, new_level
            )

        return {'new_xp': new_xp, 'new_level': new_level, 'leveled_up': new_level > old_level, 'old_level': old_level}

    async def get_user_xp(self, user_id: int) -> Optional[Dict]:
        return await self.db.fetchrow("SELECT * FROM user_xp WHERE user_id = $1", user_id)

    async def get_leaderboard_xp(self, limit: int = 10, period: str = 'all') -> List[Dict]:
        col = {'weekly': 'weekly_xp', 'monthly': 'monthly_xp'}.get(period, 'total_xp')
        return await self.db.fetch(f"""
            SELECT u.user_id, u.username, u.discord_avatar, x.total_xp, x.current_level, x.{col} as period_xp
            FROM user_xp x JOIN user_voice_data u ON x.user_id = u.user_id
            ORDER BY x.{col} DESC LIMIT $1
        """, limit)


class StreakManager:
    def __init__(self, db: DatabaseManager):
        self.db = db

    async def update_voice_streak(self, user_id: int) -> dict:
        """Call when user joins vocal. Returns {streak, multiplier}."""
        from datetime import date, timedelta
        today = date.today()

        await self.db.execute("""
            INSERT INTO user_streaks (user_id, current_streak, last_active_date)
            VALUES ($1, 1, $2)
            ON CONFLICT (user_id) DO NOTHING
        """, user_id, today)

        row = await self.db.fetchrow("SELECT * FROM user_streaks WHERE user_id = $1", user_id)
        last_date = row['last_active_date']
        current = row['current_streak']

        if last_date is None or last_date < today:
            if last_date and (today - last_date).days == 1:
                current += 1
            elif last_date and (today - last_date).days > 1:
                current = 1

            if current >= 14:
                multiplier = 2.0
            elif current >= 7:
                multiplier = 1.5
            else:
                multiplier = 1.0

            max_s = max(current, row['max_streak'] or 0)
            await self.db.execute("""
                UPDATE user_streaks
                SET current_streak = $2, max_streak = $3, last_active_date = $4, xp_multiplier = $5
                WHERE user_id = $1
            """, user_id, current, max_s, today, multiplier)

        row = await self.db.fetchrow("SELECT * FROM user_streaks WHERE user_id = $1", user_id)
        return {'streak': row['current_streak'], 'multiplier': float(row['xp_multiplier'])}

    async def get_streak(self, user_id: int) -> Optional[Dict]:
        return await self.db.fetchrow("SELECT * FROM user_streaks WHERE user_id = $1", user_id)

    async def update_message_streak(self, user_id: int) -> dict:
        from datetime import date, timedelta
        today = date.today()

        await self.db.execute("""
            INSERT INTO user_message_streaks (user_id, last_message_date, current_streak)
            VALUES ($1, $2, 1)
            ON CONFLICT (user_id) DO NOTHING
        """, user_id, today)

        row = await self.db.fetchrow("SELECT * FROM user_message_streaks WHERE user_id = $1", user_id)
        last_date = row['last_message_date']
        current = row['current_streak']

        if last_date is None or last_date < today:
            if last_date and (today - last_date).days == 1:
                current += 1
            elif last_date and (today - last_date).days > 1:
                current = 1
            max_s = max(current, row['max_streak'] or 0)
            await self.db.execute("""
                UPDATE user_message_streaks
                SET current_streak = $2, max_streak = $3, last_message_date = $4,
                    messages_today = 1
                WHERE user_id = $1
            """, user_id, current, max_s, today)
        else:
            await self.db.execute("""
                UPDATE user_message_streaks SET messages_today = messages_today + 1 WHERE user_id = $1
            """, user_id)

        row2 = await self.db.fetchrow("SELECT * FROM user_message_streaks WHERE user_id = $1", user_id)
        return {'streak': row2['current_streak'], 'messages_today': row2['messages_today']}


class QuestManager:
    def __init__(self, db: DatabaseManager):
        self.db = db

    async def get_active_quests(self) -> List[Dict]:
        from datetime import date
        return await self.db.fetch("""
            SELECT * FROM weekly_quests WHERE is_active = TRUE AND week_end >= $1
        """, date.today())

    async def update_progress(self, user_id: int, quest_type: str, increment: int = 1) -> List[Dict]:
        """Update progress for all active quests of this type. Returns completed quests."""
        quests = await self.db.fetch("""
            SELECT q.id, q.target_value, q.xp_reward, q.title, q.icon
            FROM weekly_quests q
            LEFT JOIN user_quest_progress uqp ON q.id = uqp.quest_id AND uqp.user_id = $1
            WHERE q.is_active = TRUE AND q.quest_type = $2
              AND (uqp.completed IS NULL OR uqp.completed = FALSE)
        """, user_id, quest_type)

        newly_completed = []
        for q in quests:
            await self.db.execute("""
                INSERT INTO user_quest_progress (user_id, quest_id, progress_value)
                VALUES ($1, $2, $3)
                ON CONFLICT (user_id, quest_id)
                DO UPDATE SET progress_value = user_quest_progress.progress_value + $3
            """, user_id, q['id'], increment)

            row = await self.db.fetchrow("""
                SELECT progress_value FROM user_quest_progress WHERE user_id = $1 AND quest_id = $2
            """, user_id, q['id'])

            if row and row['progress_value'] >= q['target_value']:
                result = await self.db.execute("""
                    UPDATE user_quest_progress
                    SET completed = TRUE, completed_at = NOW()
                    WHERE user_id = $1 AND quest_id = $2 AND completed = FALSE
                """, user_id, q['id'])
                if result != 'UPDATE 0':
                    newly_completed.append(dict(q))

        return newly_completed

    async def get_user_progress(self, user_id: int) -> List[Dict]:
        from datetime import date
        return await self.db.fetch("""
            SELECT q.*, COALESCE(uqp.progress_value, 0) as progress,
                   COALESCE(uqp.completed, FALSE) as completed,
                   COALESCE(uqp.xp_claimed, FALSE) as xp_claimed
            FROM weekly_quests q
            LEFT JOIN user_quest_progress uqp ON q.id = uqp.quest_id AND uqp.user_id = $1
            WHERE q.is_active = TRUE AND q.week_end >= $2
            ORDER BY q.id
        """, user_id, date.today())

    async def claim_xp(self, user_id: int, quest_id: int) -> Optional[int]:
        row = await self.db.fetchrow("""
            SELECT uqp.xp_claimed, q.xp_reward FROM user_quest_progress uqp
            JOIN weekly_quests q ON q.id = uqp.quest_id
            WHERE uqp.user_id = $1 AND uqp.quest_id = $2 AND uqp.completed = TRUE
        """, user_id, quest_id)
        if not row or row['xp_claimed']:
            return None
        await self.db.execute("""
            UPDATE user_quest_progress SET xp_claimed = TRUE WHERE user_id = $1 AND quest_id = $2
        """, user_id, quest_id)
        return row['xp_reward']

    async def create_weekly_quests(self, count: int = 8, force: bool = False):
        """Pick random templates with category diversity and create quests for the current week."""
        from datetime import date, timedelta
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)

        active = await self.db.fetchval(
            "SELECT COUNT(*) FROM weekly_quests WHERE week_start = $1 AND is_active = TRUE", week_start
        )
        if active and not force:
            return

        try:
            # At most 2 per quest_type to ensure variety
            templates = await self.db.fetch("""
                SELECT * FROM (
                    SELECT *, ROW_NUMBER() OVER (PARTITION BY quest_type ORDER BY RANDOM()) AS rn
                    FROM quest_templates WHERE is_enabled = TRUE
                ) t WHERE rn <= 2
                ORDER BY RANDOM()
                LIMIT $1
            """, count)
        except Exception:
            templates = []

        if not templates:
            templates = [
                {'title': '📬 Bavard de la semaine', 'description': 'Envoyer 200 messages',
                 'quest_type': 'messages', 'target_value': 200, 'xp_reward': 100, 'icon': '📬'},
                {'title': '🎤 Vocal de la semaine', 'description': 'Passer 5h en vocal',
                 'quest_type': 'voice_minutes', 'target_value': 300, 'xp_reward': 100, 'icon': '🎤'},
            ]

        for t in templates:
            await self.db.execute("""
                INSERT INTO weekly_quests (title, description, quest_type, target_value, xp_reward, icon, week_start, week_end)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """, t['title'], t['description'], t['quest_type'], t['target_value'],
                t['xp_reward'], t['icon'], week_start, week_end)


class NotificationManager:
    def __init__(self, db: DatabaseManager):
        self.db = db

    async def create(self, user_id: int, type_: str, title: str, description: str = None, related_id: int = None):
        await self.db.execute("""
            INSERT INTO user_notifications (user_id, type, title, description, related_id)
            VALUES ($1, $2, $3, $4, $5)
        """, user_id, type_, title, description, related_id)

    async def get_unread(self, user_id: int, limit: int = 20) -> List[Dict]:
        return await self.db.fetch("""
            SELECT * FROM user_notifications
            WHERE user_id = $1 AND read = FALSE
            ORDER BY created_at DESC LIMIT $2
        """, user_id, limit)

    async def mark_read(self, user_id: int, notification_id: int = None):
        if notification_id:
            await self.db.execute(
                "UPDATE user_notifications SET read = TRUE WHERE user_id = $1 AND id = $2",
                user_id, notification_id
            )
        else:
            await self.db.execute(
                "UPDATE user_notifications SET read = TRUE WHERE user_id = $1",
                user_id
            )


class CommandStatsManager:
    def __init__(self, db: DatabaseManager):
        self.db = db

    async def increment(self, user_id: int, command_name: str):
        await self.db.execute("""
            INSERT INTO user_command_stats (user_id, command_name, usage_count, last_used)
            VALUES ($1, $2, 1, NOW())
            ON CONFLICT (user_id, command_name)
            DO UPDATE SET usage_count = user_command_stats.usage_count + 1, last_used = NOW()
        """, user_id, command_name)

    async def get_count(self, user_id: int, command_name: str) -> int:
        return await self.db.fetchval(
            "SELECT COALESCE(usage_count, 0) FROM user_command_stats WHERE user_id = $1 AND command_name = $2",
            user_id, command_name
        ) or 0


class AchievementManager:
    def __init__(self, db: DatabaseManager):
        self.db = db

    async def check_and_unlock(self, user_id: int, condition_type: str, current_value: int) -> List[Dict]:
        """Unlock achievements whose threshold is met, return newly unlocked ones."""
        newly = await self.db.fetch("""
            SELECT a.* FROM achievements a
            WHERE a.condition_type = $1
              AND a.condition_value <= $2
              AND NOT EXISTS (
                SELECT 1 FROM user_achievements ua
                WHERE ua.user_id = $3 AND ua.achievement_id = a.id
              )
        """, condition_type, current_value, user_id)

        for a in newly:
            await self.db.execute(
                "INSERT INTO user_achievements (user_id, achievement_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                user_id, a['id']
            )
        return [dict(a) for a in newly]


class BumpManager:
    def __init__(self, db: DatabaseManager):
        self.db = db

    async def increment(self, user_id: int):
        await self.db.execute("""
            INSERT INTO user_bump_stats (user_id, bump_count)
            VALUES ($1, 1)
            ON CONFLICT (user_id)
            DO UPDATE SET bump_count = user_bump_stats.bump_count + 1, updated_at = NOW()
        """, user_id)

    async def get_count(self, user_id: int) -> int:
        return await self.db.fetchval(
            "SELECT COALESCE(bump_count, 0) FROM user_bump_stats WHERE user_id = $1", user_id
        ) or 0

    async def get_leaderboard(self, limit: int = 10) -> List[Dict]:
        return await self.db.fetch("""
            SELECT u.user_id, u.username, u.discord_avatar, b.bump_count
            FROM user_voice_data u
            JOIN user_bump_stats b ON u.user_id = b.user_id
            ORDER BY b.bump_count DESC
            LIMIT $1
        """, limit)


class InviteManager:
    def __init__(self, db: DatabaseManager):
        self.db = db

    async def increment(self, inviter_id: int):
        await self.db.execute("""
            INSERT INTO user_invite_stats (user_id, invite_count)
            VALUES ($1, 1)
            ON CONFLICT (user_id)
            DO UPDATE SET invite_count = user_invite_stats.invite_count + 1, updated_at = NOW()
        """, inviter_id)

    async def get_count(self, user_id: int) -> int:
        return await self.db.fetchval(
            "SELECT COALESCE(invite_count, 0) FROM user_invite_stats WHERE user_id = $1", user_id
        ) or 0

    async def get_leaderboard(self, limit: int = 10) -> List[Dict]:
        return await self.db.fetch("""
            SELECT u.user_id, u.username, u.discord_avatar, i.invite_count
            FROM user_voice_data u
            JOIN user_invite_stats i ON u.user_id = i.user_id
            ORDER BY i.invite_count DESC
            LIMIT $1
        """, limit)

    async def upsert_invite(self, code: str, inviter_id: int, uses: int,
                            max_uses: int | None = None,
                            expires_at=None) -> None:
        await self.db.execute("""
            INSERT INTO invite_codes (code, inviter_id, uses, max_uses, expires_at, is_active)
            VALUES ($1, $2, $3, $4, $5, TRUE)
            ON CONFLICT (code) DO UPDATE
                SET uses       = EXCLUDED.uses,
                    max_uses   = EXCLUDED.max_uses,
                    expires_at = EXCLUDED.expires_at,
                    is_active  = TRUE,
                    updated_at = NOW()
        """, code, inviter_id, uses, max_uses, expires_at)

    async def deactivate_invite(self, code: str) -> None:
        await self.db.execute(
            "UPDATE invite_codes SET is_active = FALSE, updated_at = NOW() WHERE code = $1",
            code
        )

    async def sync_all_invites(self, invites: list) -> None:
        for inv in invites:
            if inv.inviter and not inv.inviter.bot:
                await self.upsert_invite(
                    code=inv.code,
                    inviter_id=inv.inviter.id,
                    uses=inv.uses or 0,
                    max_uses=inv.max_uses or None,
                    expires_at=inv.expires_at,
                )

    async def record_use(self, invite_code: str, inviter_id: int, invitee_id: int) -> None:
        await self.db.execute("""
            INSERT INTO invite_uses (invite_code, inviter_id, invitee_id)
            VALUES ($1, $2, $3)
        """, invite_code, inviter_id, invitee_id)
        await self.db.execute("""
            UPDATE invite_codes SET uses = uses + 1, updated_at = NOW() WHERE code = $1
        """, invite_code)

    async def get_invite_stats(self) -> Dict:
        total_codes = await self.db.fetchval(
            "SELECT COUNT(*) FROM invite_codes WHERE is_active = TRUE"
        ) or 0
        total_uses = await self.db.fetchval(
            "SELECT COALESCE(SUM(uses), 0) FROM invite_codes"
        ) or 0
        uses_7d = await self.db.fetchval(
            "SELECT COUNT(*) FROM invite_uses WHERE joined_at > NOW() - INTERVAL '7 days'"
        ) or 0
        return {"total_codes": total_codes, "total_uses": total_uses, "uses_7d": uses_7d}

    async def get_top_inviters(self, limit: int = 15) -> List[Dict]:
        return await self.db.fetch("""
            SELECT v.username, iu.inviter_id, COUNT(*) AS uses
            FROM invite_uses iu
            LEFT JOIN user_voice_data v ON v.user_id = iu.inviter_id
            GROUP BY iu.inviter_id, v.username
            ORDER BY uses DESC
            LIMIT $1
        """, limit)


# ── Singletons ────────────────────────────────────────────────────────────────
db_manager            = DatabaseManager()
voice_manager         = VoiceDataManager(db_manager)
warn_manager          = WarnManager(db_manager)
message_stats_manager = MessageStatsManager(db_manager)
xp_manager            = XPManager(db_manager)
streak_manager        = StreakManager(db_manager)
quest_manager         = QuestManager(db_manager)
notification_manager  = NotificationManager(db_manager)
command_stats_manager = CommandStatsManager(db_manager)
bump_manager          = BumpManager(db_manager)
invite_manager        = InviteManager(db_manager)
achievement_manager   = AchievementManager(db_manager)


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
