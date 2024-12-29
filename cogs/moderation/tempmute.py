import discord
from discord import app_commands
from discord.ext import commands
import asyncio
from utils.constants import LOG_CHANNEL_NAME
from utils.constants import AUTHORIZED_ROLES
from utils.logging import log_command_usage

class TempMuteCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="tempmute", description="Mute temporairement un utilisateur")
    async def tempmute(self, interaction: discord.Interaction, member: discord.Member, duration: int, reason: str = None):
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
            await member.add_roles(muted_role, reason=reason)
            await interaction.response.send_message(f'{member.mention} a été muté pour {duration} minutes pour la raison: {reason if reason else "Aucune raison spécifiée."}')

            # Unmute le membre après la durée spécifiée
            await asyncio.sleep(duration * 60)  # Convertir la durée en minutes
            await member.remove_roles(muted_role, reason="Mute temporaire terminé")
            await interaction.followup.send(f'{member.mention} a été unmute.')

            # Enregistrer l'utilisation de la commande
            await log_command_usage(interaction, "tempmute", member=member, reason=reason, log_channel_name=LOG_CHANNEL_NAME)
        except Exception as e:
            await interaction.response.send_message(f"Une erreur est survenue : {e}")

async def setup(bot):
    await bot.add_cog(TempMuteCog(bot))
