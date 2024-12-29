import discord
from discord import app_commands
from discord.ext import commands
from utils.constants import LOG_CHANNEL_NAME
from utils.logging import log_command_usage

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
            await log_command_usage(interaction, "unmute", member=member, reason=reason, log_channel_name=LOG_CHANNEL_NAME)
        except Exception as e:
            await interaction.response.send_message(f"Une erreur est survenue : {e}")

async def setup(bot):
    await bot.add_cog(UnmuteCog(bot))
