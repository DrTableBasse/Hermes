"""Statistiques complètes d'un membre."""
import asyncio
import logging
import discord
from discord import app_commands
from discord.ext import commands
from utils.database import (
    voice_manager, message_stats_manager, xp_manager,
    db_manager, streak_manager, bump_manager, invite_manager,
)
from utils.command_manager import command_enabled
from utils.embed_style import hermes_embed, progress_bar, Colors

logger = logging.getLogger(__name__)


class StatsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="stats", description="Voir les statistiques complètes d'un membre")
    @command_enabled(guild_specific=True)
    async def stats_cmd(self, interaction: discord.Interaction, user: discord.Member = None):
        await interaction.response.defer()
        target = user or interaction.user

        voice_data, total_msgs, xp_data, streak_data, bumps, invites = await asyncio.gather(
            voice_manager.get_user(target.id),
            message_stats_manager.get_total(target.id),
            xp_manager.get_user_xp(target.id),
            streak_manager.get_streak(target.id),
            bump_manager.get_count(target.id),
            invite_manager.get_count(target.id),
        )
        warn_count, ach_count = await asyncio.gather(
            db_manager.fetchval("SELECT COUNT(*) FROM warn WHERE user_id = $1", target.id),
            db_manager.fetchval("SELECT COUNT(*) FROM user_achievements WHERE user_id = $1", target.id),
        )

        voice_rank = await db_manager.fetchval("""
            SELECT COUNT(*) + 1 FROM user_voice_data
            WHERE total_time > COALESCE(
                (SELECT total_time FROM user_voice_data WHERE user_id = $1), 0
            )
        """, target.id)

        msg_rank = await db_manager.fetchval("""
            SELECT COUNT(*) + 1 FROM (
                SELECT user_id, SUM(message_count) AS total
                FROM user_message_stats GROUP BY user_id
            ) sub WHERE total > COALESCE(
                (SELECT SUM(message_count) FROM user_message_stats WHERE user_id = $1), 0
            )
        """, target.id)

        embed = hermes_embed(
            title=f"📊  Stats — {target.display_name}",
            color=Colors.BLUE,
            thumbnail_url=target.display_avatar.url,
        )

        # Voice
        s = voice_data['total_time'] if voice_data else 0
        h, rem = divmod(s, 3600)
        m, _ = divmod(rem, 60)
        embed.add_field(
            name="🎤 Vocal",
            value=f"**{h}h {m}m**\n*#{voice_rank} au classement*",
            inline=True,
        )

        # Messages
        embed.add_field(
            name="💬 Messages",
            value=f"**{total_msgs:,}**\n*#{msg_rank} au classement*",
            inline=True,
        )

        # Warnings
        embed.add_field(
            name="⚠️ Avertissements",
            value=f"**{warn_count or 0}**",
            inline=True,
        )

        # XP & Level
        if xp_data:
            level = xp_data['current_level']
            xp = xp_data['total_xp']
            next_xp = xp_manager.xp_for_level(level + 1)
            bar = progress_bar(xp, next_xp, length=8)
            embed.add_field(
                name="⚡ Niveau & XP",
                value=f"Niv. **{level}** · **{xp:,}** XP\n{bar}",
                inline=False,
            )

        # Streak
        if streak_data:
            current = streak_data['current_streak'] or 0
            record = streak_data['max_streak'] or 0
            multi = float(streak_data['xp_multiplier'] or 1.0)
            streak_icon = "🔥🔥🔥" if current >= 14 else "🔥🔥" if current >= 7 else "🔥" if current >= 1 else "❄️"
            embed.add_field(
                name=f"{streak_icon} Streak vocal",
                value=f"**{current}** jours · record **{record}** · ×{multi:.1f}",
                inline=True,
            )

        # Bumps
        embed.add_field(name="🔔 Bumps", value=f"**{bumps}**", inline=True)

        # Invites
        embed.add_field(name="📨 Invitations", value=f"**{invites}** membres", inline=True)

        # Achievements
        embed.add_field(name="🏆 Achievements", value=f"**{ach_count or 0}** débloqués", inline=True)

        join_date = target.joined_at.strftime('%d/%m/%Y') if target.joined_at else '?'
        embed.set_footer(text=f"Membre depuis le {join_date}  ·  Hermes · SaucisseLand")

        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(StatsCog(bot))
