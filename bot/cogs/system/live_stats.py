"""Relevés du serveur pour la caserne en direct du site.

- toutes les 5 min : relevé (effectifs, connectés, vocal, messages depuis le précédent) ;
- toutes les minutes : battement de cœur ;
- une fois par jour : purge des données de plus de 30 jours.
Le compteur de messages est incrémenté par ``main.on_message``.
"""
import logging
import os

import discord
from discord.ext import commands, tasks

from cogs.fun.game_lfg import GAMES
from utils import settings
from utils.database import db_manager
from utils.live_stats import MemberView, MessageCounter, summarize

logger = logging.getLogger(__name__)

GAME_ROLES = {key: game["role_name"] for key, game in GAMES.items()}


class LiveStats(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.counter = MessageCounter()
        self.snapshot_task.start()
        self.heartbeat_task.start()
        self.purge_task.start()

    def cog_unload(self):
        self.snapshot_task.cancel()
        self.heartbeat_task.cancel()
        self.purge_task.cancel()

    def count_message(self) -> None:
        self.counter.increment()

    def collect(self, guild: discord.Guild) -> dict:
        """État instantané du serveur (relevé et ``GET /live``)."""
        views = (
            MemberView(
                is_bot=m.bot,
                online=m.status != discord.Status.offline,
                in_voice=m.voice is not None and m.voice.channel is not None,
                avatar_url=m.display_avatar.url,
                role_names=frozenset(r.name for r in m.roles),
            )
            for m in guild.members
        )
        return summarize(views, GAME_ROLES)

    def _guild(self):
        return self.bot.get_guild(int(os.getenv('GUILD_ID', '0')))

    async def _wait_ready(self):
        await self.bot.wait_until_ready()
        await settings.ready.wait()

    # ── Tâches ───────────────────────────────────────────────────────────────

    @tasks.loop(minutes=5)
    async def snapshot_task(self):
        # Pas de relevé d'exception : une erreur hors réseau arrêterait la boucle définitivement.
        messages = 0
        try:
            guild = self._guild()
            if not guild:
                return
            state = self.collect(guild)
            messages = self.counter.take()
            await db_manager.execute(
                "INSERT INTO guild_stats_snapshots (members, online, in_voice, messages) "
                "VALUES ($1, $2, $3, $4)",
                state["members"], state["online"], state["in_voice"], messages,
            )
        except Exception:
            self.counter.give_back(messages)
            logger.exception("Relevé du serveur en échec")

    @snapshot_task.before_loop
    async def _before_snapshot(self):
        await self._wait_ready()

    @tasks.loop(minutes=1)
    async def heartbeat_task(self):
        try:
            await db_manager.execute(
                "INSERT INTO bot_heartbeats VALUES (date_trunc('minute', NOW())) ON CONFLICT DO NOTHING"
            )
        except Exception:
            logger.exception("Battement de cœur en échec")

    @heartbeat_task.before_loop
    async def _before_heartbeat(self):
        await self._wait_ready()

    @tasks.loop(hours=24)
    async def purge_task(self):
        try:
            await db_manager.execute(
                "DELETE FROM guild_stats_snapshots WHERE taken_at < NOW() - INTERVAL '30 days'")
            await db_manager.execute(
                # 31 j : garde « depuis » (première minute) ≥ 30 j une fois la fenêtre atteinte,
                # sinon la purge ferait repasser la disponibilité à « depuis le … » en boucle.
                "DELETE FROM bot_heartbeats WHERE minute < NOW() - INTERVAL '31 days'")
        except Exception:
            logger.exception("Purge des relevés en échec")

    @purge_task.before_loop
    async def _before_purge(self):
        await self._wait_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(LiveStats(bot))
