import discord
from discord import app_commands
from discord.ext import commands
from config import CONFESSION_CHANNEL_ID
from utils.logging import log_confession, log_command
from utils.command_manager import CommandStatusManager, command_enabled
import logging

logger = logging.getLogger("fun_commands")

class ConfessionCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="confession", description="Faites une confession anonyme")
    @command_enabled(guild_specific=True)
    @log_command()
    async def confession(self, interaction: discord.Interaction, message: str):
        command_name = interaction.command.name
        is_enabled = await CommandStatusManager.get_command_status(command_name, guild_id=interaction.guild_id, use_cache=False)
        logger.info(f"[{command_name}] Appel de la commande. Statut: {'activée' if is_enabled else 'désactivée'}")
        if not is_enabled:
            logger.warning(f"[{command_name}] Commande désactivée, accès refusé à {interaction.user} (id={interaction.user.id})")
            await interaction.response.send_message(
                f"❌ La commande `/{command_name}` est actuellement désactivée.",
                ephemeral=True
            )
            return
        try:
            # Log métier : log_confession (utile pour garder la trace des confessions)
            await log_confession(interaction.user, message, log_channel_id=CONFESSION_CHANNEL_ID)
            await interaction.response.send_message(
                "✅ Votre confession a bien été envoyée anonymement !",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"[{command_name}] Erreur lors de l'envoi de la confession: {e}")
            await interaction.response.send_message(
                f"❌ Une erreur est survenue lors de l'envoi de la confession : {e}",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(ConfessionCog(bot))
