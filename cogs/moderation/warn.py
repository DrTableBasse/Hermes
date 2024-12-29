import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
import time
from utils.logging import log_sanction
from utils.constants import DB_PATH


class WarnCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="warn", description="Avertir un utilisateur avec une raison spécifique")
    async def warn(self, interaction: discord.Interaction, user: discord.Member, reason: str):
        # Vérifier si l'utilisateur a la permission de gérer les messages
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("Vous n'avez pas les permissions nécessaires pour utiliser cette commande.", ephemeral=True)
            return

        # Connexion à la base de données SQLite
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Vérifier si l'utilisateur existe déjà dans la table user_voice_data
        cursor.execute('SELECT user_id FROM user_voice_data WHERE user_id = ?', (user.id,))
        result = cursor.fetchone()

        if not result:
            # Insérer l'utilisateur dans la table user_voice_data s'il n'existe pas
            cursor.execute('''
                INSERT INTO user_voice_data (user_id, username)
                VALUES (?, ?)
            ''', (user.id, str(user)))

        # Insérer l'avertissement dans la table warn
        cursor.execute('''
            INSERT INTO warn (user_id, reason, create_time)
            VALUES (?, ?, ?)
        ''', (user.id, reason, int(time.time())))

        conn.commit()
        conn.close()

        # Notification à l'utilisateur et au modérateur
        await interaction.response.send_message(f"{user.mention} a été averti pour la raison suivante : {reason}.")
        try:
            await user.send(f"Vous avez été averti sur le serveur {interaction.guild.name} pour la raison suivante : {reason}.")
        except discord.Forbidden:
            await interaction.followup.send("Impossible d'envoyer un message privé à l'utilisateur.")

        # Log de la sanction avec la raison, l'auteur de la commande et l'utilisateur concerné
        log_message = f"Raison : {reason}"
        action_taken_by = interaction.user.display_name  # Nom d'affichage de l'utilisateur qui a exécuté la commande
        await log_sanction(
            user,
            "averti",
            reason=log_message,
            log_channel_name="sanctions",
            action_taken_by=action_taken_by  # Ajouter l'auteur de la commande au log
        )

async def setup(bot):
    await bot.add_cog(WarnCog(bot))
