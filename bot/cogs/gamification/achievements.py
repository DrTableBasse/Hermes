"""Affiche les achievements débloqués d'un membre."""
import logging
import discord
from discord import app_commands
from discord.ext import commands

from utils.database import db_manager
from utils.command_manager import command_enabled
from utils.embed_style import hermes_embed, Colors

logger = logging.getLogger(__name__)


def _tier(points: int) -> tuple[int, str]:
    if points >= 100:
        return Colors.GOLD,   "Légendaire"
    if points >= 50:
        return Colors.BLUE,   "Épique"
    if points >= 25:
        return Colors.ORANGE, "Rare"
    return Colors.GREY,       "Commun"


_TIER_EMOJI = {
    "Légendaire": "⭐",
    "Épique":     "💎",
    "Rare":       "🔶",
    "Commun":     "⚪",
}


class AchievementsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="achievements",
        description="Voir les achievements débloqués d'un membre",
    )
    @command_enabled(guild_specific=True)
    async def achievements_cmd(
        self,
        interaction: discord.Interaction,
        user: discord.Member = None,
    ):
        await interaction.response.defer()
        target = user or interaction.user

        rows = await db_manager.fetch("""
            SELECT a.name, a.description, a.icon, a.points, ua.unlocked_at
            FROM user_achievements ua
            JOIN achievements a ON a.id = ua.achievement_id
            WHERE ua.user_id = $1
            ORDER BY a.points DESC, ua.unlocked_at ASC
        """, target.id)

        total_pts = sum(r["points"] for r in rows)
        count = len(rows)

        embed = hermes_embed(
            title=f"🏆  Achievements — {target.display_name}",
            description=(
                f"**{count}** achievement{'s' if count != 1 else ''} débloqué{'s' if count != 1 else ''} "
                f"· **{total_pts} pts**"
            ),
            color=Colors.GOLD,
            thumbnail_url=target.display_avatar.url,
        )

        if not rows:
            embed.add_field(
                name="Aucun achievement",
                value="Participe au serveur pour débloquer tes premiers achievements !",
                inline=False,
            )
        else:
            tier_groups: dict[str, list[str]] = {
                "Légendaire": [], "Épique": [], "Rare": [], "Commun": [],
            }
            for r in rows:
                _, label = _tier(r["points"])
                icon = r["icon"] or "🏆"
                date_str = r["unlocked_at"].strftime("%d/%m/%Y") if r["unlocked_at"] else "?"
                line = f"{icon} **{r['name']}** · {r['points']} pts · *{date_str}*"
                tier_groups[label].append(line)

            for label in ("Légendaire", "Épique", "Rare", "Commun"):
                entries = tier_groups[label]
                if not entries:
                    continue
                display = entries[:15]
                value = "\n".join(display)
                if len(entries) > 15:
                    value += f"\n*…et {len(entries) - 15} de plus*"
                embed.add_field(
                    name=f"{_TIER_EMOJI[label]} {label}  ({len(entries)})",
                    value=value,
                    inline=False,
                )

        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(AchievementsCog(bot))
