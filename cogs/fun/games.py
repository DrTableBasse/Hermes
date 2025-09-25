import discord
from discord import app_commands
from discord.ext import commands
import random
from utils.command_manager import CommandStatusManager, command_enabled
from utils.logging import log_command
import logging

logger = logging.getLogger("fun_commands")

class GamesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="coinflip", description="Faire un pile ou face")
    @command_enabled(guild_specific=True)
    @log_command()
    async def coinflip(self, interaction: discord.Interaction):
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
            # (Log automatique géré par command_logger.py)
            # Effectuer le tirage
            result = 'pile' if random.randint(0, 1) == 0 else 'face'
            await interaction.response.send_message(f"🪙 Le résultat est {result} !")
        except Exception as e:
            logger.error(f"[{command_name}] Erreur lors de l'exécution de la commande coinflip")
            await interaction.response.send_message(f"❌ Erreur lors de l'exécution de la commande coinflip", ephemeral=True)

async def setup(bot):
    await bot.add_cog(GamesCog(bot))
