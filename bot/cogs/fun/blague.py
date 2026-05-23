import logging
import os

import discord
from discord import app_commands
from discord.ext import commands
from utils.command_manager import command_enabled
from utils.logging import log_command
from utils.embed_style import hermes_embed, Colors

logger = logging.getLogger(__name__)


class BlagueCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="blague", description="Raconter une blague aléatoire")
    @command_enabled(guild_specific=True)
    @log_command()
    async def blague(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            from blagues_api import BlaguesAPI
            api = BlaguesAPI(os.getenv('BLAGUES_API_TOKEN', ''))
            joke = await api.random()
            embed = hermes_embed(
                title="😄  Blague du jour",
                description=f"**{joke.joke}**\n\n||{joke.answer}||",
                color=Colors.YELLOW,
            )
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"[blague] {e}", exc_info=True)
            await interaction.followup.send(
                embed=hermes_embed(description="❌ Impossible de récupérer une blague.", color=Colors.RED),
                ephemeral=True,
            )


async def setup(bot):
    await bot.add_cog(BlagueCog(bot))
