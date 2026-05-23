"""Système de streaks vocaux quotidiens."""
import logging
import discord
from discord import app_commands
from discord.ext import commands
from utils.database import streak_manager
from utils.command_manager import command_enabled
from utils.embed_style import hermes_embed, Colors

logger = logging.getLogger(__name__)


class StreaksCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="streak", description="Afficher votre streak vocal")
    @command_enabled(guild_specific=True)
    async def streak_cmd(self, interaction: discord.Interaction, user: discord.Member = None):
        target = user or interaction.user
        data = await streak_manager.get_streak(target.id)

        if data and data['current_streak'] >= 14:
            color = Colors.RED
            streak_icon = "🔥🔥🔥"
        elif data and data['current_streak'] >= 7:
            color = Colors.ORANGE
            streak_icon = "🔥🔥"
        elif data and data['current_streak'] >= 1:
            color = Colors.YELLOW
            streak_icon = "🔥"
        else:
            color = Colors.GREY
            streak_icon = "❄️"

        embed = hermes_embed(
            title=f"{streak_icon}  Streak Vocal  ─  {target.display_name}",
            color=color,
            thumbnail_url=target.display_avatar.url,
        )
        if data:
            multiplier = float(data['xp_multiplier'])
            embed.add_field(name="Streak actuel", value=f"**{data['current_streak']}** jours", inline=True)
            embed.add_field(name="Record", value=f"🏆 **{data['max_streak']}** jours", inline=True)
            embed.add_field(name="Multiplicateur", value=f"✨ **x{multiplier:.1f}**", inline=True)
            if data['current_streak'] >= 14:
                embed.set_footer(text="Multiplicateur x2.0 actif !  ·  Hermes · SaucisseLand")
            elif data['current_streak'] >= 7:
                embed.set_footer(text="Multiplicateur x1.5 actif !  ·  Hermes · SaucisseLand")
        else:
            embed.description = "Aucune donnée de streak. Rejoins un vocal pour commencer !"

        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(StreaksCog(bot))
