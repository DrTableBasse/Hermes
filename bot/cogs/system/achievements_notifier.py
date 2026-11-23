"""Notifie les utilisateurs quand un achievement est débloqué ; le rôle passe par les règles."""
import logging
import os
import discord
from discord.ext import commands

from utils.database import db_manager, notification_manager

logger = logging.getLogger(__name__)

GUILD_ID = int(os.getenv('GUILD_ID', '0'))


class AchievementsNotifier(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _member(self, guild: discord.Guild, user_id: int) -> discord.Member | None:
        member = guild.get_member(user_id)
        if member is None:
            try:
                member = await guild.fetch_member(user_id)
            except (discord.NotFound, discord.HTTPException):
                member = None
        return member

    async def notify(self, user_id: int, achievement_id: int):
        try:
            ach = await db_manager.fetchrow(
                "SELECT * FROM achievements WHERE id = $1", achievement_id
            )
            if not ach:
                return

            name = ach['name']
            desc = ach['description'] or ''

            # ── Rôle de succès : règle « créer au premier déblocage » (cog RoleEngine)
            guild = self.bot.get_guild(GUILD_ID)
            engine = self.bot.get_cog('RoleEngine')
            if guild and engine:
                member = await self._member(guild, user_id)
                if member:
                    await engine.evaluate_member(member)

            await notification_manager.create(
                user_id, 'achievement',
                f"Achievement débloqué : {name}",
                desc,
                achievement_id,
            )

        except Exception as e:
            logger.error(f"notify achievement error: {e}", exc_info=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(AchievementsNotifier(bot))
