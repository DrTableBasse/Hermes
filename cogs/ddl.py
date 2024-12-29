import discord
import os
import re
import subprocess
from discord import app_commands
from discord.ext import commands
from utils.constants import LOG_CHANNEL_NAME
from utils.logging import log_command_usage
from concurrent.futures import ThreadPoolExecutor

class DDL_Cog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.download_directories = {
            'Drames': '/home/jellyfin/dsk/jellyfin/Films-Triés/Drames',
            'Action': '/home/jellyfin/dsk/jellyfin/Films-Triés/Action',
            'Animé': '/home/jellyfin/dsk/jellyfin/Manga',
            'SF': '/home/jellyfin/dsk/jellyfin/Films-Triés/SF',
            'Comédie': '/home/jellyfin/dsk/jellyfin/Films-Triés/Comédie',
            'Horreur': '/home/jellyfin/dsk/jellyfin/Films-Triés/Horreur'
        }
        self.executor = ThreadPoolExecutor(max_workers=5)

    @app_commands.command(name="ddl", description="Télécharge un film à partir d'une URL")
    async def ddl(self, interaction: discord.Interaction, url: str, nom_du_film: str, categorie: str):
        if categorie not in self.download_directories:
            await interaction.response.send_message(f'Catégorie invalide. Les catégories valides sont : {", ".join(self.download_directories.keys())}')
            return

        if not re.match(r'^[a-zA-Z0-9-_]+$', nom_du_film):
            await interaction.response.send_message('Nom du film invalide. Le nom ne doit contenir que des lettres, chiffres, tirets et underscores.')
            return

        destination_directory = self.download_directories[categorie]
        if not os.path.exists(destination_directory):
            os.makedirs(destination_directory)
        destination_path = os.path.join(destination_directory, f'{nom_du_film}.mp4')

        await interaction.response.send_message(f'Téléchargement de {nom_du_film} ({categorie}) en cours....')

        def download(url, destination_path):
            command = ['uqload_downloader', url, destination_path]
            try:
                result = subprocess.run(command, capture_output=True, text=True)
                if result.returncode == 0:
                    return f'Téléchargement terminé de : {nom_du_film}'
                else:
                    return f'Erreur lors du téléchargement : {result.stderr}'
            except Exception as e:
                return f'Erreur lors de l\'exécution de la commande : {str(e)}'

        future = self.executor.submit(download, url, destination_path)
        message = await interaction.loop.run_in_executor(None, future.result)
        await interaction.followup.send(message)

async def setup(bot):
    await bot.add_cog(DDL_Cog(bot))
