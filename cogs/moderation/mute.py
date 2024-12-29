import discord
from discord import app_commands
from discord.ext import commands
import json
from utils.constants import LOG_CHANNEL_NAME
from utils.logging import log_command_usage

class MuteCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def is_command_enabled(self, command_name: str):
        # Charger la liste des commandes depuis list-commands.json
        try:
            with open("list-commands.json", "r") as f:
                commands_data = json.load(f)
            return commands_data.get(command_name, False)  # Retourne True si activée, False sinon
        except FileNotFoundError:
            return False

    @app_commands.command(name="mute", description="Mute un utilisateur dans le serveur")
    async def mute(self, interaction: discord.Interaction, member: discord.Member, reason: str = None):
        # Vérifier si la commande est activée
        if not await self.is_command_enabled("mute"):
            await interaction.response.send_message("La commande /mute est actuellement désactivée.", ephemeral=True)
            return

        # Vérifier si l'utilisateur a la permission de gérer les rôles
        if not interaction.user.guild_permissions.manage_roles:
            await interaction.response.send_message("Vous n'avez pas les permissions nécessaires pour utiliser cette commande.", ephemeral=True)
            return

        try:
            # Assurer que le rôle "Muted" existe
            muted_role = discord.utils.get(interaction.guild.roles, name="mute")
            if not muted_role:
                muted_role = await interaction.guild.create_role(name="mute", reason="Role needed for mute functionality")
                for channel in interaction.guild.channels:
                    await channel.set_permissions(muted_role, send_messages=False, speak=False)
                    print("mute role created")

            # Ajouter le rôle "Muted" au membre
            await member.add_roles(muted_role, reason=reason)
            await interaction.response.send_message(f'{member.mention} a été muté pour la raison: {reason if reason else "Aucune raison spécifiée."}')
            await log_command_usage(interaction, "mute", member=member, reason=reason, log_channel_name=LOG_CHANNEL_NAME)
        except Exception as e:
            await interaction.response.send_message(f"Une erreur est survenue : {e}")

async def setup(bot):
    await bot.add_cog(MuteCog(bot))
