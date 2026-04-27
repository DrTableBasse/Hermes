import discord
from discord import app_commands
from discord.ext import commands
from utils.command_manager import command_enabled
from utils.logging import log_command
import os


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
            embed = discord.Embed(title="😄 Blague du jour", color=discord.Color.yellow())
            embed.add_field(name="Question", value=joke.joke,   inline=False)
            embed.add_field(name="Réponse",  value=f"||{joke.answer}||", inline=False)
            await interaction.followup.send(embed=embed)
        except Exception:
            await interaction.followup.send("❌ Impossible de récupérer une blague.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(BlagueCog(bot))
