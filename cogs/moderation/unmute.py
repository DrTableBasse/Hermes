import discord
from discord import app_commands
from discord.ext import commands
from config import LOG_CHANNEL_ID
from utils.logging import log_command_usage, log_command
from datetime import datetime
from utils.command_manager import command_enabled
import logging

logger = logging.getLogger(__name__)

class UnmuteCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="unmute", description="Unmute un utilisateur dans le serveur")
    async def unmute(self, interaction: discord.Interaction, member: discord.Member, reason: str = None):
        # Vérifie si l'utilisateur a l'un des rôles autorisés
        # if not any(role.name in AUTHORIZED_ROLES for role in interaction.user.roles):
        #     await interaction.response.send_message("Vous n'avez pas les permissions nécessaires pour utiliser cette commande.", ephemeral=True)
        #     return

        try:
            # Vérifier si le rôle "mute" existe
            muted_role = discord.utils.get(interaction.guild.roles, name="mute")
            if not muted_role:
                await interaction.response.send_message("Le rôle 'Muted' n'existe pas.", ephemeral=True)
                return

            # Retirer le rôle "mute" du membre
            await member.remove_roles(muted_role, reason=reason)
            await interaction.response.send_message(f'{member.mention} a été unmute.')
            await log_command_usage(interaction, "unmute", member=member, reason=reason, log_channel_id=LOG_CHANNEL_ID)
        except Exception as e:
            logger.error(f"[unmute] Erreur lors de l'exécution de la commande unmute")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(f"Une erreur est survenue lors de l'unmute de l'utilisateur", ephemeral=True)
                else:
                    await interaction.followup.send(f"Une erreur est survenue lors de l'unmute de l'utilisateur", ephemeral=True)
            except Exception as send_err:
                logger.error(f"[unmute] Impossible d'envoyer le message d'erreur : {send_err}")

async def setup(bot):
    await bot.add_cog(UnmuteCog(bot))
