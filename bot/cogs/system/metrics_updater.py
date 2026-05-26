"""Periodic refresh of Prometheus metrics gauges."""
import logging
from discord.ext import commands, tasks
import metrics as bot_metrics

logger = logging.getLogger(__name__)


class MetricsUpdaterCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.refresh_metrics.start()

    def cog_unload(self):
        self.refresh_metrics.cancel()

    @tasks.loop(seconds=60)
    async def refresh_metrics(self):
        bot_metrics.bot_ready.set(1 if self.bot.is_ready() else 0)
        await bot_metrics.refresh()

    @refresh_metrics.before_loop
    async def before_refresh(self):
        await self.bot.wait_until_ready()
        await bot_metrics.refresh()
        logger.info("Prometheus metrics initialized")


async def setup(bot):
    await bot.add_cog(MetricsUpdaterCog(bot))
