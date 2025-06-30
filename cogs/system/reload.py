import discord
from discord import app_commands
from discord.ext import commands
from utils.constants import cogs_names
from datetime import datetime
from utils.command_manager import command_enabled
from utils.logging import log_command
import logging

logger = logging.getLogger(__name__)

class ReloadCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        


    @app_commands.command(name="reload", description="Recharge tous les cogs")
    @command_enabled(guild_specific=True)
    async def reload(self, interaction: discord.Interaction):

        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("Vous n'avez pas les permissions nécessaires pour utiliser cette commande.", ephemeral=True)
            

        for cog in cogs_names():
            try:
                await self.bot.unload_extension(f'{cog}')
                await self.bot.load_extension(f'{cog}')
                #print(f'Reloaded {cog}')
            except Exception as e:
                logger.error(f"[reload] Erreur lors de l'exécution: {e}")
                try:
                    if not interaction.response.is_done():
                        await interaction.response.send_message(f"Une erreur est survenue lors du rechargement de {cog}: {e}", ephemeral=True)
                    else:
                        await interaction.followup.send(f"Une erreur est survenue lors du rechargement de {cog}: {e}", ephemeral=True)
                except Exception as send_err:
                    logger.error(f"[reload] Impossible d'envoyer le message d'erreur : {send_err}")

        await interaction.response.send_message("Tous les cogs ont été rechargés.")

async def setup(bot):
    await bot.add_cog(ReloadCog(bot))
