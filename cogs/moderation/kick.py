import discord
from discord import app_commands
from discord.ext import commands
import json
from utils.constants import LOG_CHANNEL_NAME
from utils.logging import log_command_usage

class KickCog(commands.Cog):
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

    @app_commands.command(name="kick", description="Kick un utilisateur du serveur")
    async def kick(self, interaction: discord.Interaction, member: discord.Member, reason: str = None):
        # Vérifier si la commande est activée
        if not await self.is_command_enabled("kick"):
            await interaction.response.send_message("La commande /kick est actuellement désactivée.", ephemeral=True)
            return

        if not interaction.user.guild_permissions.kick_members:
            await interaction.response.send_message("Vous n'avez pas les permissions nécessaires pour utiliser cette commande.", ephemeral=True)
            return

        try:
            await member.kick(reason=reason)
            await interaction.response.send_message(f'{member.mention} a été expulsé pour la raison: {reason if reason else "Aucune raison spécifiée."}')
            await log_command_usage(interaction, "kick", member=member, reason=reason, log_channel_name=LOG_CHANNEL_NAME)
        except Exception as e:
            await interaction.response.send_message(f"Une erreur est survenue : {e}")

async def setup(bot):
    await bot.add_cog(KickCog(bot))
