import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
from utils.command_manager import command_enabled
from utils.logging import log_command

class ShutdownCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="shutdown", description="Éteindre le bot")
    @command_enabled(guild_specific=True)
    @log_command()
    async def shutdown(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Vous n'avez pas les permissions nécessaires pour utiliser cette commande.", ephemeral=True)
            return

        await interaction.response.send_message("Le bot est en train de s'arrêter...")
        await self.bot.close()

async def setup(bot):
    await bot.add_cog(ShutdownCog(bot))
