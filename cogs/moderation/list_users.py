import discord
from discord import app_commands
from discord.ext import commands
import json
import os
from utils.constants import LOG_CHANNEL_NAME
from utils.logging import log_command_usage

class ListAndMessageUsersCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.commands_file = 'list-commands.json'  # Fichier pour stocker les commandes existantes

    async def add_command_to_json(self, command_name):
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
        if os.path.exists(self.commands_file):
            with open(self.commands_file, 'r') as f:
                commands_data = json.load(f)
            if command_name in commands_data and not commands_data[command_name]:
                return True
        return False

    @app_commands.command(
        name="list_and_message_users",
        description="Liste tous les utilisateurs (hors bots) et leur envoie un message personnalisé."
    )
    async def list_and_message_users(self, interaction: discord.Interaction, message: str):
        if await self.check_command_disabled("list_and_message_users"):
            await interaction.response.send_message("La commande `/list_and_message_users` est actuellement désactivée.", ephemeral=True)
            return

        try:
            members = interaction.guild.members  # Récupère tous les membres du serveur
            filename = "ListeUtilisateurs.txt"
            with open(filename, "w", encoding="utf-8") as file:
                for member in members:
                    if not member.bot:  # Vérifie si le membre n'est pas un bot
                        # Envoie un message direct au membre
                        try:
                            await member.send(message)
                            file.write(f"{member.name}#{member.discriminator} (ID: {member.id}) - Message envoyé avec succès\n")
                        except Exception as e:
                            file.write(f"{member.name}#{member.discriminator} (ID: {member.id}) - Échec de l'envoi : {e}\n")

            # Envoie le fichier avec les résultats
            await interaction.response.send_message(
                "Liste des utilisateurs (hors bots) et état des messages envoyés :",
                file=discord.File(filename)
            )
            await log_command_usage(interaction, "list_and_message_users", log_channel_name=LOG_CHANNEL_NAME)
        except Exception as e:
            await interaction.response.send_message(f"Une erreur est survenue : {e}")

    async def setup(self):
        await self.add_command_to_json("list_and_message_users")

async def setup(bot):
    cog = ListAndMessageUsersCog(bot)
    await cog.setup()
    await bot.add_cog(cog)
