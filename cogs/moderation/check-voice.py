import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
from config import DB_PATH
import json

class CheckVoiceCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _get_db_connection(self):
        return sqlite3.connect(DB_PATH)

    async def is_command_enabled(self, command_name: str):
        # Charger la liste des commandes depuis list-commands.json
        try:
            with open("list-commands.json", "r") as f:
                commands_data = json.load(f)
            return commands_data.get(command_name, False)  # Retourne True si activée, False sinon
        except FileNotFoundError:
            return False

    @app_commands.command(name='check-voice', description='Vérifie le temps total passé en vocal')
    async def check_voice(self, interaction: discord.Interaction):
        # Vérifier si la commande est activée
        if not await self.is_command_enabled("check-voice"):
            await interaction.response.send_message("La commande /check-voice est actuellement désactivée.", ephemeral=True)
            return

        user_id = interaction.user.id

        conn = self._get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('SELECT total_time, username FROM user_voice_data WHERE user_id = ?', (user_id,))
            row = cursor.fetchone()
            if row:
                total_time_seconds = row[0]
                username = row[1]

                # Convert total time in seconds to hours, minutes, and seconds
                hours, remainder = divmod(total_time_seconds, 3600)
                minutes, seconds = divmod(remainder, 60)

                # Format the duration string
                duration_str = f"{hours}h {minutes}m {seconds}s"

                # Create and send the embed
                embed = discord.Embed(
                    title="Temps Vocal Total",
                    description=f"Voici le temps total que vous avez passé en vocal, {interaction.user.mention}.",
                    color=discord.Color.blue()
                )
                embed.add_field(name="Utilisateur", value=username, inline=False)
                embed.add_field(name="Temps Total", value=duration_str, inline=False)
                await interaction.response.send_message(embed=embed)
            else:
                await interaction.response.send_message("Aucune donnée trouvée pour votre ID utilisateur.\nLe bot fonctionne de la façon suivante :\n- Quand c'est la première fois que vous vous connectez, il faut déco-reco du vocal.\n- Refaire la commande `/check-voice`")

        except sqlite3.Error as e:
            await interaction.response.send_message(f"[ERROR] Une erreur est survenue lors de la récupération des données : {e}")
        finally:
            conn.close()

async def setup(bot):
    await bot.add_cog(CheckVoiceCog(bot))
