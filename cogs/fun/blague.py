import discord
from discord import app_commands
from discord.ext import commands
import json
import os
from utils.constants import LOG_CHANNEL_NAME
from utils.logging import log_command_usage
from blagues_api import BlaguesAPI
from config import TOKEN_BLAGUE_API

class BlaguesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.blagues = TOKEN_BLAGUE_API
        self.commands_file = 'list-commands.json'  # Fichier pour stocker les commandes existantes

    async def add_command_to_json(self, command_name):
        # Ajoute le nom de la commande à list-commands.json si ce n'est pas déjà fait
        if os.path.exists(self.commands_file):
            with open(self.commands_file, 'r') as f:
                commands_data = json.load(f)
        else:
            commands_data = {}

        if command_name not in commands_data:
            commands_data[command_name] = True  # La commande est activée par défaut

        with open(self.commands_file, 'w') as f:
            json.dump(commands_data, f, indent=4)

    async def check_command_disabled(self, command_name):
        # Vérifie si la commande est désactivée en lisant list-commands.json
        if os.path.exists(self.commands_file):
            with open(self.commands_file, 'r') as f:
                commands_data = json.load(f)
            if command_name in commands_data and not commands_data[command_name]:
                return True
        return False

    @app_commands.command(name="blague", description="Dit une blague aléatoire")
    async def blague(self, interaction: discord.Interaction):
        if await self.check_command_disabled("blague"):
            await interaction.response.send_message("La commande `/blague` est actuellement désactivée.", ephemeral=True)
            return
        
        try:
            # Assurez-vous que 'random' est une coroutine
            blague = await self.blagues.random()
            # Envoie de la blague
            await interaction.response.send_message(f'{blague.joke}')
            # Envoie de la réponse en spoiler
            await interaction.followup.send(f'||{blague.answer}||')
            # Enregistrement de la commande
            await log_command_usage(interaction, "blague", log_channel_name=LOG_CHANNEL_NAME)
        except Exception as e:
            # Envoi d'un message d'erreur en cas d'exception
            await interaction.response.send_message(f"Une erreur est survenue : {e}")

    async def setup(self):
        # Lors du chargement du cog, on ajoute la commande dans le fichier list-commands.json
        await self.add_command_to_json("blague")

async def setup(bot):
    cog = BlaguesCog(bot)
    await cog.setup()  # Ajouter la commande au fichier JSON lors du chargement du cog
    await bot.add_cog(cog)
