import discord
from discord import app_commands
from discord.ext import commands
import asyncio
from utils.constants import LOG_CHANNEL_ID
from utils.constants import AUTHORIZED_ROLES
from utils.logging import log_command_usage, log_command
from datetime import datetime, timedelta
from utils.command_manager import command_enabled
import logging

logger = logging.getLogger(__name__)

class TempMuteCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="tempmute", description="Mute temporairement un utilisateur")
    @command_enabled(guild_specific=True)
    async def tempmute(self, interaction: discord.Interaction, user: discord.Member, duration: int, unit: str, reason: str = "Aucune raison spécifiée"):
        # Vérifie si l'utilisateur a l'un des rôles autorisés
        if not any(role.name in AUTHORIZED_ROLES for role in interaction.user.roles):
            await interaction.response.send_message("Vous n'avez pas les permissions nécessaires pour utiliser cette commande.", ephemeral=True)
            return

        try:
            # Vérifier si le rôle "mute" existe, sinon le créer
            muted_role = discord.utils.get(interaction.guild.roles, name="mute")
            if not muted_role:
                muted_role = await interaction.guild.create_role(name="mute", reason="Role needed for mute functionality")
                for channel in interaction.guild.channels:
                    await channel.set_permissions(muted_role, send_messages=False, speak=False)

            # Ajouter le rôle "mute" au membre
            await user.add_roles(muted_role, reason=reason)
            await interaction.response.send_message(f'{user.mention} a été muté pour {duration} {unit} pour la raison: {reason if reason else "Aucune raison spécifiée."}')

            # Unmute le membre après la durée spécifiée
            await asyncio.sleep(duration * 60)  # Convertir la durée en minutes
            await user.remove_roles(muted_role, reason="Mute temporaire terminé")
            await interaction.followup.send(f'{user.mention} a été unmute.')

            # Enregistrer l'utilisation de la commande
            await log_command_usage(interaction, "tempmute", member=user, reason=reason, log_channel_id=LOG_CHANNEL_ID)
        except Exception as e:
            logger.error(f"[tempmute] Erreur lors de l'exécution: {e}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(f"Une erreur est survenue : {e}", ephemeral=True)
                else:
                    await interaction.followup.send(f"Une erreur est survenue : {e}", ephemeral=True)
            except Exception as send_err:
                logger.error(f"[tempmute] Impossible d'envoyer le message d'erreur : {send_err}")

async def setup(bot):
    await bot.add_cog(TempMuteCog(bot))
