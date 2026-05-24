"""Classement unifié — toutes catégories."""
import logging
import discord
from discord import app_commands
from discord.ext import commands
from utils.database import (
    voice_manager, message_stats_manager, xp_manager,
    db_manager, streak_manager, bump_manager, invite_manager,
)
from utils.command_manager import command_enabled
from utils.embed_style import leaderboard_embed

logger = logging.getLogger(__name__)

MEDALS = {0: "🥇", 1: "🥈", 2: "🥉"}

CATEGORIES = [
    app_commands.Choice(name="XP",          value="xp"),
    app_commands.Choice(name="Vocal",        value="vocal"),
    app_commands.Choice(name="Messages",     value="messages"),
    app_commands.Choice(name="Bumps",        value="bumps"),
    app_commands.Choice(name="Invitations",  value="invitations"),
    app_commands.Choice(name="Streaks",      value="streaks"),
    app_commands.Choice(name="Achievements", value="achievements"),
    app_commands.Choice(name="Global",       value="global"),
]

META = {
    "xp":           ("⚡", "Classement XP"),
    "vocal":        ("🎤", "Classement Vocal"),
    "messages":     ("💬", "Classement Messages"),
    "bumps":        ("🔔", "Classement Bumps"),
    "invitations":  ("📨", "Classement Invitations"),
    "streaks":      ("🔥", "Classement Streaks"),
    "achievements": ("🏆", "Classement Achievements"),
    "global":       ("🌟", "Classement Global"),
}


def _prefix(i: int) -> str:
    return MEDALS.get(i, f"`{i + 1}.`")


def _fmt_time(seconds: int) -> str:
    h, r = divmod(seconds or 0, 3600)
    m, _ = divmod(r, 60)
    return f"{h}h {m}m"


class ClassementCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="classement", description="Classement du serveur")
    @app_commands.choices(categorie=CATEGORIES)
    @command_enabled(guild_specific=True)
    async def classement_cmd(
        self,
        interaction: discord.Interaction,
        categorie: app_commands.Choice[str] = None,
    ):
        await interaction.response.defer()
        cat = categorie.value if categorie else "xp"
        icon, title = META[cat]
        entries = await self._build_entries(cat)
        await interaction.followup.send(embed=leaderboard_embed(title, entries, icon=icon))

    async def _build_entries(self, cat: str) -> list[str]:
        if cat == "xp":
            rows = await xp_manager.get_leaderboard_xp(10)
            return [
                f"{_prefix(i)} **{r['username']}** — Niv. {r['current_level']} · {r['total_xp']:,} XP"
                for i, r in enumerate(rows)
            ]

        if cat == "vocal":
            rows = await voice_manager.get_leaderboard(10)
            return [
                f"{_prefix(i)} **{r['username']}** — {_fmt_time(r['total_time'])}"
                for i, r in enumerate(rows)
            ]

        if cat == "messages":
            rows = await message_stats_manager.get_leaderboard(10)
            return [
                f"{_prefix(i)} **{r['username']}** — {r['total_messages']:,} messages"
                for i, r in enumerate(rows)
            ]

        if cat == "bumps":
            rows = await bump_manager.get_leaderboard(10)
            return [
                f"{_prefix(i)} **{r['username']}** — {r['bump_count']} bumps"
                for i, r in enumerate(rows)
            ]

        if cat == "invitations":
            rows = await invite_manager.get_leaderboard(10)
            return [
                f"{_prefix(i)} **{r['username']}** — {r['invite_count']} invités"
                for i, r in enumerate(rows)
            ]

        if cat == "streaks":
            rows = await db_manager.fetch("""
                SELECT u.username, s.current_streak, s.max_streak
                FROM user_streaks s
                JOIN user_voice_data u ON s.user_id = u.user_id
                ORDER BY s.current_streak DESC, s.max_streak DESC
                LIMIT 10
            """)
            return [
                f"{_prefix(i)} **{r['username']}** — 🔥 {r['current_streak']} jours · record {r['max_streak']}"
                for i, r in enumerate(rows)
            ]

        if cat == "achievements":
            rows = await db_manager.fetch("""
                SELECT u.username, COUNT(ua.achievement_id) AS total
                FROM user_voice_data u
                JOIN user_achievements ua ON u.user_id = ua.user_id
                GROUP BY u.user_id, u.username
                ORDER BY total DESC
                LIMIT 10
            """)
            return [
                f"{_prefix(i)} **{r['username']}** — 🏆 {r['total']} achievements"
                for i, r in enumerate(rows)
            ]

        if cat == "global":
            # 1pt/min vocal + 1pt/message + 200pt/achievement
            rows = await db_manager.fetch("""
                SELECT
                    u.username,
                    COALESCE(u.total_time / 60, 0)
                    + COALESCE(msg.total_messages, 0)
                    + COALESCE(ach.ach_count * 200, 0) AS score
                FROM user_voice_data u
                LEFT JOIN (
                    SELECT user_id, SUM(message_count) AS total_messages
                    FROM user_message_stats GROUP BY user_id
                ) msg ON u.user_id = msg.user_id
                LEFT JOIN (
                    SELECT user_id, COUNT(*) AS ach_count
                    FROM user_achievements GROUP BY user_id
                ) ach ON u.user_id = ach.user_id
                ORDER BY score DESC
                LIMIT 10
            """)
            return [
                f"{_prefix(i)} **{r['username']}** — {r['score']:,} pts"
                for i, r in enumerate(rows)
            ]

        return ["*Catégorie inconnue.*"]


async def setup(bot):
    await bot.add_cog(ClassementCog(bot))
