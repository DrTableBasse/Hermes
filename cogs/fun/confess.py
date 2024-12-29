import discord
from discord import app_commands
from discord.ext import commands
from utils.constants import LOG_CHANNEL_NAME, CONFESSION_CHANNEL_NAME
from utils.logging import log_confession
import json

class ConfessionCog(commands.Cog):
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

    @app_commands.command(name="confession", description="Faites une confession anonyme")
    async def confession(self, interaction: discord.Interaction, message: str):
        # Vérifier si la commande est activée
        if not await self.is_command_enabled("confession"):
            await interaction.response.send_message("La commande /confession est actuellement désactivée.", ephemeral=True)
            return

        try:
            # Récupération des salons pour la confession
            confession_channel = discord.utils.get(interaction.guild.text_channels, name=CONFESSION_CHANNEL_NAME)

            # Envoi de la confession dans le salon dédié
            if confession_channel:
                await confession_channel.send(f"📢 **Confession :** {message}")
            else:
                await interaction.response.send_message(f"Le salon de confession n'a pas été trouvé.", ephemeral=True)
                return

            # Log de la confession avec la nouvelle fonction
            await log_confession(interaction.user, message, log_channel_name=LOG_CHANNEL_NAME)

            # Réponse à l'utilisateur (éphemère pour rester confidentiel)
            await interaction.response.send_message("Votre confession a été envoyée avec succès.", ephemeral=True)

        except Exception as e:
            # Gestion des erreurs
            await interaction.response.send_message(f"Une erreur est survenue : {e}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(ConfessionCog(bot))
