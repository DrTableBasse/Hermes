"""Rafraîchissement périodique des métriques Prometheus."""
import logging
import os
from discord.ext import commands, tasks
import metrics as bot_metrics

logger = logging.getLogger(__name__)


class MetricsUpdaterCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.refresh_metrics.start()

    def cog_unload(self):
        self.refresh_metrics.cancel()

    def _guild(self):
        return self.bot.get_guild(int(os.getenv('GUILD_ID', '0')))

    @tasks.loop(seconds=60)
    async def refresh_metrics(self):
        bot_metrics.bot_ready.set(1 if self.bot.is_ready() else 0)
        await bot_metrics.refresh(guild=self._guild())

    @refresh_metrics.before_loop
    async def before_refresh(self):
        await self.bot.wait_until_ready()
        bot_metrics.bot_ready.set(1)
        await bot_metrics.refresh(guild=self._guild())
        logger.info("Prometheus metrics initialized")


async def setup(bot):
    await bot.add_cog(MetricsUpdaterCog(bot))
