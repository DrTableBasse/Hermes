import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
import json

class CheckWarnCog(commands.Cog):
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

    @app_commands.command(name="check-warn", description="Vérifier les trois derniers avertissements d'un utilisateur")
    async def check_warn(self, interaction: discord.Interaction, user: discord.Member):
        # Vérifier si la commande est activée
        if not await self.is_command_enabled("check-warn"):
            await interaction.response.send_message("La commande /check-warn est actuellement désactivée.", ephemeral=True)
            return

        # Vérifier les permissions de l'utilisateur
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("Vous n'avez pas les permissions nécessaires pour utiliser cette commande.", ephemeral=True)
            return

        # Connect to the SQLite database
        conn = sqlite3.connect('voice_data.db')
        cursor = conn.cursor()

        # Retrieve the last three warns for the specified user
        cursor.execute('''
            SELECT reason, datetime(create_time, 'unixepoch', 'localtime') as warn_time
            FROM warn
            WHERE user_id = ?
            ORDER BY create_time DESC
            LIMIT 3
        ''', (user.id,))
        warns = cursor.fetchall()

        conn.close()

        # If no warns are found
        if not warns:
            await interaction.response.send_message(f"{user.mention} n'a pas d'avertissements.")
            return

        # Construct the response message
        warn_list = "\n".join([f"**{i+1}.** Raison : {warn[0]} - Date : {warn[1]}" for i, warn in enumerate(warns)])
        response_message = f"Voici les trois derniers avertissements pour {user.mention} :\n\n{warn_list}"

        # Send the response message
        await interaction.response.send_message(response_message)

async def setup(bot):
    await bot.add_cog(CheckWarnCog(bot))
