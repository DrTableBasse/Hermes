import discord
from discord import app_commands
from discord.ext import commands
from utils.constants import LOG_CHANNEL_NAME
from utils.logging import log_command_usage, log_command
from datetime import datetime
from utils.command_manager import command_enabled
import logging

logger = logging.getLogger(__name__)

class ListAndMessageUsersCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="list-users",
        description="Lister tous les utilisateurs du serveur avec leurs rôles"
    )
    @command_enabled(guild_specific=True)
    async def list_users(self, interaction: discord.Interaction):
        try:
            if not interaction.guild:
                await interaction.response.send_message("Cette commande ne peut être utilisée que dans un serveur.", ephemeral=True)
                return
            members = interaction.guild.members  # Récupère tous les membres du serveur
            filename = "ListeUtilisateurs.txt"
            with open(filename, "w", encoding="utf-8") as file:
                for member in members:
                    if not member.bot:  # Vérifie si le membre n'est pas un bot
                        # Affiche les informations du membre
                        roles = [role.name for role in member.roles if role.name != "@everyone"]
                        file.write(f"{member.name}#{member.discriminator} (ID: {member.id}) - Rôles: {', '.join(roles) if roles else 'Aucun rôle'}\n")

            # Envoie le fichier avec les résultats
            await interaction.response.send_message(
                "Liste des utilisateurs (hors bots) avec leurs rôles :",
                file=discord.File(filename)
            )
            await log_command_usage(interaction, "list_users")
        except Exception as e:
            logger.error(f"[list_users] Erreur lors de l'exécution: {e}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(f"Une erreur est survenue : {e}", ephemeral=True)
                else:
                    await interaction.followup.send(f"Une erreur est survenue : {e}", ephemeral=True)
            except Exception as send_err:
                logger.error(f"[list_users] Impossible d'envoyer le message d'erreur : {send_err}")

async def setup(bot):
    await bot.add_cog(ListAndMessageUsersCog(bot))
