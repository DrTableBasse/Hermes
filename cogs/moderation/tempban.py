import discord
from discord import app_commands
from discord.ext import commands
import asyncio

class TempBanCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="tempban", description="Bannir temporairement un utilisateur")
    @app_commands.describe(unit="Unité de temps (secondes, minutes, heures, jours, mois, années)")
    async def tempban(self, interaction: discord.Interaction, member: discord.Member, duration: int, unit: str, reason: str = None):
        if not interaction.user.guild_permissions.ban_members:
            await interaction.response.send_message("Vous n'avez pas les permissions nécessaires pour utiliser cette commande.", ephemeral=True)
            return

        # Convertir la durée en secondes
        unit = unit.lower()
        if unit in ["secondes", "seconde"]:
            duration_seconds = duration
        elif unit in ["minutes", "minute"]:
            duration_seconds = duration * 60
        elif unit in ["heures", "heure"]:
            duration_seconds = duration * 60 * 60
        elif unit in ["jours", "jour"]:
            duration_seconds = duration * 60 * 60 * 24
        elif unit in ["mois", "mois"]:
            duration_seconds = duration * 60 * 60 * 24 * 30
        elif unit in ["années", "année"]:
            duration_seconds = duration * 60 * 60 * 24 * 365
        else:
            await interaction.response.send_message("Unité de temps invalide. Utilisez 'secondes', 'minutes', 'heures', 'jours', 'mois', ou 'années'.", ephemeral=True)
            return

        try:
            await member.ban(reason=reason, delete_message_days=7)
            await interaction.response.send_message(f'{member.mention} a été banni pour {duration} {unit} pour la raison: {reason if reason else "Aucune raison spécifiée."}')

            # Créer une tâche pour débannir le membre après la durée spécifiée
            self.bot.loop.create_task(self.temp_unban(member, duration_seconds, interaction.guild))

        except Exception as e:
            await interaction.response.send_message(f"Une erreur est survenue : {e}")

    async def temp_unban(self, member, duration, guild):
        await asyncio.sleep(duration)
        try:
            await guild.unban(member, reason="Bannissement temporaire terminé")
        except Exception as e:
            print(f"Une erreur est survenue lors du débannissement de {member}: {e}")

    @app_commands.autocomplete(name="unit")
    async def unit_autocomplete(self, interaction: discord.Interaction, current: str):
        units = ["secondes", "minutes", "heures", "jours", "mois", "années"]
        return [
            app_commands.Choice(name=unit, value=unit)
            for unit in units if current.lower() in unit.lower()
        ]

async def setup(bot):
    await bot.add_cog(TempBanCog(bot))
