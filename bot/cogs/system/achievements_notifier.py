"""Notifie les utilisateurs via DM quand un achievement est débloqué."""
import logging
from datetime import datetime

import discord
from discord.ext import commands

from utils.database import db_manager, notification_manager
from utils.embed_style import Colors, FOOTER_TEXT

logger = logging.getLogger(__name__)


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

    async def notify(self, user_id: int, achievement_id: int):
        try:
            ach = await db_manager.fetchrow(
                "SELECT * FROM achievements WHERE id = $1", achievement_id
            )
            if not ach:
                return

            color, tier_label = _tier(ach['points'])
            icon  = ach['icon'] or '🏆'
            name  = ach['name']
            desc  = ach['description'] or ''
            pts   = ach['points']

            embed = discord.Embed(
                title=f"{icon}  {name}",
                description=desc,
                color=color,
                timestamp=datetime.now(),
            )
            embed.add_field(name="✨ Points gagnés", value=f"**+{pts} pts**",     inline=True)
            embed.add_field(name="🎖️ Rareté",        value=tier_label,            inline=True)
            embed.set_footer(text=f"Achievement débloqué  ·  {FOOTER_TEXT}")

            discord_user = self.bot.get_user(user_id) or await self.bot.fetch_user(user_id)
            try:
                await discord_user.send(embed=embed)
            except discord.Forbidden:
                pass
            except Exception as e:
                logger.warning(f"DM achievement failed for {user_id}: {e}")

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
