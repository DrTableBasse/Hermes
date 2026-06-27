"""Notifie les utilisateurs via DM et attribue un rôle quand un achievement est débloqué."""
import asyncio
import logging
import os
import discord
from discord.ext import commands, tasks

from utils.database import db_manager, notification_manager
from utils.embed_style import Colors

logger = logging.getLogger(__name__)

GUILD_ID = int(os.getenv('GUILD_ID', '0'))

# Couleurs Discord pour chaque tier
_TIER_ROLE_COLORS = {
    "Légendaire": discord.Color(Colors.GOLD),
    "Épique":     discord.Color(Colors.BLUE),
    "Rare":       discord.Color(Colors.ORANGE),
    "Commun":     discord.Color(Colors.GREY),
}


def _tier(points: int) -> tuple[int, str]:
    if points >= 100:
        return Colors.GOLD,   "Légendaire"
    if points >= 50:
        return Colors.BLUE,   "Épique"
    if points >= 25:
        return Colors.ORANGE, "Rare"
    return Colors.GREY,       "Commun"


class AchievementsNotifier(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._backfill_done = False
        self.backfill_roles.start()

    def cog_unload(self):
        self.backfill_roles.cancel()

    @tasks.loop(count=1)
    async def backfill_roles(self):
        """Attribue silencieusement les rôles achievements à tous les membres qui les ont déjà."""
        await self.bot.wait_until_ready()
        guild = self.bot.get_guild(GUILD_ID)
        if not guild:
            logger.warning("Backfill achievements : guild introuvable")
            return

        rows = await db_manager.fetch("""
            SELECT ua.user_id, a.name, a.icon, a.points
            FROM user_achievements ua
            JOIN achievements a ON a.id = ua.achievement_id
        """)
        if not rows:
            return

        # Pré-créer tous les rôles distincts d'abord
        role_cache: dict[str, discord.Role | None] = {}
        seen = set()
        for r in rows:
            key = f"{r['icon'] or '🏆'} {r['name']}"
            if key not in seen:
                seen.add(key)
                _, tier_label = _tier(r['points'])
                color = _TIER_ROLE_COLORS.get(tier_label, discord.Color(Colors.GREY))
                role_cache[key] = await self._ensure_role(guild, key, color)
                await asyncio.sleep(0.3)  # respect rate limits

        assigned = 0
        for r in rows:
            role_name = f"{r['icon'] or '🏆'} {r['name']}"
            role = role_cache.get(role_name)
            if not role:
                continue
            member = guild.get_member(r['user_id'])
            if member and role not in member.roles:
                try:
                    await member.add_roles(role, reason="Backfill achievements")
                    assigned += 1
                    await asyncio.sleep(0.1)
                except discord.Forbidden:
                    pass
                except discord.HTTPException:
                    await asyncio.sleep(1)

        logger.info(f"Backfill achievements terminé : {assigned} rôles attribués sur {len(rows)} entrées")

    async def _ensure_role(self, guild: discord.Guild, role_name: str, color: discord.Color) -> discord.Role | None:
        """Retourne le rôle existant ou le crée."""
        role = discord.utils.get(guild.roles, name=role_name)
        if role:
            return role
        try:
            role = await guild.create_role(
                name=role_name,
                color=color,
                reason="Rôle achievement créé automatiquement par Hermes",
            )
            logger.info(f"Rôle achievement créé : '{role_name}'")
            return role
        except discord.Forbidden:
            logger.warning(f"Permissions insuffisantes pour créer le rôle '{role_name}'")
            return None
        except Exception as e:
            logger.error(f"Erreur création rôle '{role_name}': {e}")
            return None

    async def notify(self, user_id: int, achievement_id: int):
        try:
            ach = await db_manager.fetchrow(
                "SELECT * FROM achievements WHERE id = $1", achievement_id
            )
            if not ach:
                return

            _, tier_label = _tier(ach['points'])
            icon  = ach['icon'] or '🏆'
            name  = ach['name']
            desc  = ach['description'] or ''

            # ── Rôle achievement ──────────────────────────────────────────
            guild = self.bot.get_guild(GUILD_ID)
            if guild:
                role_name = f"{icon} {name}"
                role_color = _TIER_ROLE_COLORS.get(tier_label, discord.Color(Colors.GREY))
                role = await self._ensure_role(guild, role_name, role_color)
                if role:
                    member = guild.get_member(user_id)
                    if member is None:
                        try:
                            member = await guild.fetch_member(user_id)
                        except (discord.NotFound, discord.HTTPException):
                            member = None
                    if member and role not in member.roles:
                        try:
                            await member.add_roles(role, reason=f"Achievement débloqué : {name}")
                            logger.info(f"Rôle '{role_name}' attribué à {user_id}")
                        except discord.Forbidden:
                            logger.warning(f"Impossible d'attribuer le rôle '{role_name}' à {user_id}")

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
