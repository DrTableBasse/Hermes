import discord
import os
import re
import subprocess
from discord import app_commands
from discord.ext import commands
from utils.constants import LOG_CHANNEL_NAME, directories
from utils.logging import log_command_usage
import json

class DDLCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.download_directories = directories

    async def is_command_enabled(self, command_name: str):
        # Charger la liste des commandes depuis list-commands.json
        try:
            with open("list-commands.json", "r") as f:
                commands_data = json.load(f)
            return commands_data.get(command_name, False)  # Retourne True si activée, False sinon
        except FileNotFoundError:
            return False

    @app_commands.command(name="ddl", description="Télécharge un film à partir d'une URL")
    async def ddl(self, interaction: discord.Interaction, url: str, nom_du_film: str, categorie: str):
        # Vérifier si la commande est activée
        if not await self.is_command_enabled("ddl"):
            await interaction.response.send_message("La commande /ddl est actuellement désactivée.", ephemeral=True)
            return

        # Log de la commande
        await log_command_usage(
            interaction=interaction,
            command_name="ddl",
            member=interaction.user,
            reason=f'URL: {url}, Nom du film: {nom_du_film}, Catégorie: {categorie}',
            log_channel_name=LOG_CHANNEL_NAME
        )

        if categorie not in self.download_directories:
            await interaction.response.send_message(f'Catégorie invalide. Les catégories valides sont : {", ".join(self.download_directories.keys())}')
            return

        # Vérification du nom du film avec la regex
        if not re.match(r'^[a-zA-Z0-9-_]+$', nom_du_film):
            await interaction.response.send_message('Nom du film invalide. Le nom ne doit contenir que des lettres, chiffres, tirets et underscores.')
            return

        # Obtenir le répertoire de destination en fonction de la catégorie
        destination_directory = self.download_directories[categorie]
        if not os.path.exists(destination_directory):
            os.makedirs(destination_directory)
        destination_path = os.path.join(destination_directory, f'{nom_du_film}.mp4')

        await interaction.response.send_message(f'Téléchargement de {nom_du_film} ({categorie}) en cours...')

        # Construire et exécuter la commande de téléchargement
        command = ['uqload_downloader', url, destination_path]
        try:
            result = subprocess.run(command, capture_output=True, text=True)
            if result.returncode == 0:
                await interaction.followup.send(f'Téléchargement terminé de : {nom_du_film}')
            else:
                await interaction.followup.send(f'Erreur lors du téléchargement : {result.stderr}')
        except Exception as e:
            await interaction.followup.send(f'Erreur lors de l\'exécution de la commande : {str(e)}')

async def setup(bot):
    await bot.add_cog(DDLCog(bot))
