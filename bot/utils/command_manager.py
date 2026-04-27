import asyncio
import functools
import os
from datetime import datetime, timedelta
from typing import Dict, Optional
import discord
from utils.database import db_manager

CACHE: Dict[str, bool] = {}
CACHE_EXPIRY: Dict[str, datetime] = {}
CACHE_TTL = timedelta(minutes=5)


class CommandStatusManager:

    @staticmethod
    def _key(name: str, guild_id: Optional[int]) -> str:
        return f"{name}_{guild_id}" if guild_id else name

    @staticmethod
    async def get(name: str, guild_id: Optional[int] = None, use_cache: bool = True) -> bool:
        key = CommandStatusManager._key(name, guild_id)
        if use_cache and key in CACHE and datetime.now() < CACHE_EXPIRY.get(key, datetime.min):
            return CACHE[key]

        try:
            if not db_manager._pool:
                await db_manager.initialize()
            async with db_manager.get_connection() as conn:
                if guild_id:
                    row = await conn.fetchrow(
                        "SELECT is_enabled FROM command_status WHERE command_name=$1 AND guild_id=$2",
                        name, guild_id
                    )
                else:
                    row = await conn.fetchrow(
                        "SELECT is_enabled FROM command_status WHERE command_name=$1 AND guild_id IS NULL",
                        name
                    )
                status = row['is_enabled'] if row else True
                if not row:
                    await CommandStatusManager.set(name, True, guild_id)
                CACHE[key] = status
                CACHE_EXPIRY[key] = datetime.now() + CACHE_TTL
                return status
        except Exception as e:
            print(f"[CommandStatus] get error: {e}")
            return True

    @staticmethod
    async def set(name: str, enabled: bool, guild_id: Optional[int] = None) -> bool:
        try:
            if not db_manager._pool:
                await db_manager.initialize()
            async with db_manager.get_connection() as conn:
                await conn.execute("""
                    INSERT INTO command_status (command_name, guild_id, is_enabled, updated_at)
                    VALUES ($1, $2, $3, NOW())
                    ON CONFLICT (command_name, guild_id)
                    DO UPDATE SET is_enabled = EXCLUDED.is_enabled, updated_at = NOW()
                """, name, guild_id, enabled)
            key = CommandStatusManager._key(name, guild_id)
            CACHE.pop(key, None)
            CACHE_EXPIRY.pop(key, None)
            return True
        except Exception as e:
            print(f"[CommandStatus] set error: {e}")
            return False

    @staticmethod
    async def get_all(guild_id: Optional[int] = None) -> Dict[str, bool]:
        try:
            if not db_manager._pool:
                await db_manager.initialize()
            async with db_manager.get_connection() as conn:
                if guild_id:
                    rows = await conn.fetch(
                        "SELECT command_name, is_enabled FROM command_status WHERE guild_id=$1 OR guild_id IS NULL",
                        guild_id
                    )
                else:
                    rows = await conn.fetch(
                        "SELECT command_name, is_enabled FROM command_status WHERE guild_id IS NULL"
                    )
            return {r['command_name']: r['is_enabled'] for r in rows}
        except Exception:
            return {}


def command_enabled(guild_specific: bool = False):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(self, interaction: discord.Interaction, *args, **kwargs):
            name = getattr(interaction.command, 'name', func.__name__)
            guild_id = interaction.guild_id if guild_specific else None
            enabled = await CommandStatusManager.get(name, guild_id, use_cache=False)
            if not enabled:
                await interaction.response.send_message(
                    f"❌ La commande `/{name}` est actuellement désactivée.", ephemeral=True
                )
                return
            return await func(self, interaction, *args, **kwargs)
        return wrapper
    return decorator


async def init_command_status_table():
    if not db_manager._pool:
        await db_manager.initialize()
    async with db_manager.get_connection() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS command_status (
                id SERIAL PRIMARY KEY,
                command_name VARCHAR(100) NOT NULL,
                guild_id BIGINT,
                is_enabled BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE(command_name, guild_id)
            )
        """)
    print("✅ Table command_status prête")
