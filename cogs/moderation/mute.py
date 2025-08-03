import discord
from discord import app_commands
from discord.ext import commands
from config import LOG_CHANNEL_ID
from utils.logging import log_command_usage, log_command
from datetime import datetime
from utils.command_manager import command_enabled
import logging

logger = logging.getLogger(__name__)

class MuteCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="mute", description="Mute un utilisateur dans le serveur")
    @command_enabled(guild_specific=True)
    @log_command()
    async def mute(self, interaction: discord.Interaction, user: discord.Member, reason: str = "Aucune raison spécifiée"):
        # Vérifier si l'utilisateur a la permission de gérer les rôles
        if not interaction.user.guild_permissions.manage_roles:
            await interaction.response.send_message("Vous n'avez pas les permissions nécessaires pour utiliser cette commande.", ephemeral=True)
            return

        try:
            if not interaction.guild:
                await interaction.response.send_message("Cette commande ne peut être utilisée que dans un serveur.", ephemeral=True)
                return
                
            # Assurer que le rôle "Muted" existe
            muted_role = discord.utils.get(interaction.guild.roles, name="mute")
            if not muted_role:
                muted_role = await interaction.guild.create_role(name="mute", reason="Role needed for mute functionality")
                for channel in interaction.guild.channels:
                    await channel.set_permissions(muted_role, send_messages=False, speak=False)
                    print("mute role created")

            # Ajouter le rôle "Muted" au membre
            await user.add_roles(muted_role, reason=reason)
            await interaction.response.send_message(f'{user.mention} a été muté pour la raison: {reason if reason else "Aucune raison spécifiée."}')
            await log_command_usage(interaction, "mute", member=user, reason=reason, log_channel_id=LOG_CHANNEL_ID)
        except Exception as e:
            logger.error(f"[mute] Erreur lors de l'exécution: {e}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(f"Une erreur est survenue : {e}", ephemeral=True)
                else:
                    await interaction.followup.send(f"Une erreur est survenue : {e}", ephemeral=True)
            except Exception as send_err:
                logger.error(f"[mute] Impossible d'envoyer le message d'erreur : {send_err}")

async def setup(bot):
    await bot.add_cog(MuteCog(bot))
