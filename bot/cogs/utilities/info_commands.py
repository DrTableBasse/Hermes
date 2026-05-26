"""Commandes d'information rapide."""
import logging
import discord
from discord import app_commands
from discord.ext import commands
from utils.database import voice_manager, message_stats_manager, xp_manager, db_manager, streak_manager
from utils.command_manager import command_enabled
from utils.embed_style import hermes_embed, leaderboard_embed, Colors

logger = logging.getLogger(__name__)


class InfoCommandsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="profile", description="Voir le profil complet d'un membre")
    @command_enabled(guild_specific=True)
    async def profile(self, interaction: discord.Interaction, user: discord.Member = None):
        await interaction.response.defer()
        target = user or interaction.user

        voice_data = await voice_manager.get_user(target.id)
        total_msgs = await message_stats_manager.get_total(target.id)
        xp_data = await xp_manager.get_user_xp(target.id)
        streak_data = await streak_manager.get_streak(target.id)
        warn_count = await db_manager.fetchval(
            "SELECT COUNT(*) FROM warn WHERE user_id = $1", target.id
        ) or 0
        ach_count = await db_manager.fetchval(
            "SELECT COUNT(*) FROM user_achievements WHERE user_id = $1", target.id
        ) or 0

        embed = hermes_embed(
            title=f"👤  {target.display_name}",
            color=Colors.BLUE,
            thumbnail_url=target.display_avatar.url,
        )

        # Voice
        s = voice_data['total_time'] if voice_data else 0
        h, r = divmod(s, 3600)
        m, _ = divmod(r, 60)

        embed.add_field(name="🎤 Vocal", value=f"**{h}**h **{m}**m", inline=True)
        embed.add_field(name="💬 Messages", value=f"**{total_msgs:,}**", inline=True)
        embed.add_field(name="⚠️ Warns", value=f"**{warn_count}**", inline=True)

        if xp_data:
            embed.add_field(name="⚡ Niveau", value=f"**{xp_data['current_level']}**", inline=True)
            embed.add_field(name="✨ XP", value=f"**{xp_data['total_xp']:,}**", inline=True)

        if streak_data:
            current = streak_data['current_streak'] or 0
            record  = streak_data['max_streak'] or 0
            multi   = float(streak_data['xp_multiplier'] or 1.0)
            streak_icon = "🔥🔥🔥" if current >= 14 else "🔥🔥" if current >= 7 else "🔥" if current >= 1 else "❄️"
            embed.add_field(
                name=f"{streak_icon} Streak vocal",
                value=f"**{current}** jours · record **{record}** · ×{multi:.1f}",
                inline=True,
            )

        embed.add_field(name="🏆 Achievements", value=f"**{ach_count}**", inline=True)

        join_date = target.joined_at.strftime('%d/%m/%Y') if target.joined_at else '?'
        embed.set_footer(text=f"Membre depuis le {join_date}  ·  Hermes · SaucisseLand")

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="top-today", description="Top 5 du jour (messages et vocal)")
    @command_enabled(guild_specific=True)
    async def top_today(self, interaction: discord.Interaction):
        await interaction.response.defer()
        top_xp = await xp_manager.get_leaderboard_xp(5, 'weekly')
        top_voice = await voice_manager.get_leaderboard(5)

        medals = {0: "🥇", 1: "🥈", 2: "🥉"}

        embed = hermes_embed(
            title="🏆  Actifs de la semaine",
            color=Colors.GOLD,
        )

        voice_lines = []
        for i, row in enumerate(top_voice):
            s = row['total_time']
            h, r = divmod(s, 3600)
            m, _ = divmod(r, 60)
            prefix = medals.get(i, f"`{i+1}.`")
            voice_lines.append(f"{prefix} **{row['username']}** — {h}h {m}m")
        embed.add_field(
            name="🎤 Top Vocal",
            value="\n".join(voice_lines) or "*Aucune donnée*",
            inline=True,
        )

        xp_lines = []
        for i, row in enumerate(top_xp):
            prefix = medals.get(i, f"`{i+1}.`")
            xp_lines.append(f"{prefix} **{row['username']}** — {row['period_xp']:,} XP")
        embed.add_field(
            name="⚡ Top XP",
            value="\n".join(xp_lines) or "*Aucune donnée*",
            inline=True,
        )

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="compare", description="Comparer deux membres")
    @command_enabled(guild_specific=True)
    async def compare(self, interaction: discord.Interaction, user1: discord.Member, user2: discord.Member):
        await interaction.response.defer()

        async def get_stats(u):
            vd = await voice_manager.get_user(u.id)
            msgs = await message_stats_manager.get_total(u.id)
            xp = await xp_manager.get_user_xp(u.id)
            return vd, msgs, xp

        vd1, m1, x1 = await get_stats(user1)
        vd2, m2, x2 = await get_stats(user2)

        def fmt_time(s):
            h, r = divmod(s or 0, 3600)
            m, _ = divmod(r, 60)
            return f"{h}h {m}m"

        def fmt_stat(vd, m, x):
            return (
                f"🎤 **{fmt_time(vd['total_time'] if vd else 0)}**\n"
                f"💬 **{m:,}** msgs\n"
                f"⚡ Niv. **{x['current_level'] if x else 1}**"
            )

        embed = hermes_embed(
            title="⚔️  Comparaison",
            color=Colors.RED,
        )
        embed.add_field(name=user1.display_name, value=fmt_stat(vd1, m1, x1), inline=True)
        embed.add_field(name="⚔️", value="**VS**", inline=True)
        embed.add_field(name=user2.display_name, value=fmt_stat(vd2, m2, x2), inline=True)
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(InfoCommandsCog(bot))
