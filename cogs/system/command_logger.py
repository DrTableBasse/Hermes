import discord
from discord.ext import commands
from utils.logging import log_all_commands, log_admin_action
import logging

logger = logging.getLogger(__name__)

ADMIN_COMMANDS = ["warn", "kick", "ban", "mute", "tempban", "tempmute", "clear", "unmute"]

class CommandLoggerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        """Log les erreurs de commandes"""
        try:
            if isinstance(error, commands.CommandNotFound):
                logger.info(f"Commande non trouvée: {ctx.message.content} par {ctx.author.display_name}")
            elif isinstance(error, commands.MissingPermissions):
                logger.warning(f"Permissions insuffisantes pour {ctx.command.name} par {ctx.author.display_name}")
            else:
                logger.error(f"Erreur de commande {ctx.command.name}: {error}")
        except Exception as e:
            logger.error(f"Erreur lors du log d'erreur de commande: {e}")

async def setup(bot):
    await bot.add_cog(CommandLoggerCog(bot)) 