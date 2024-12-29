import discord
from discord import app_commands
from discord.ext import commands
import json

class ClearCog(commands.Cog):
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

    @app_commands.command(name="clear", description="Supprimer un nombre spécifié de messages")
    async def clear(self, interaction: discord.Interaction, amount: int):
        # Vérifier si la commande est activée
        if not await self.is_command_enabled("clear"):
            await interaction.response.send_message("La commande /clear est actuellement désactivée.", ephemeral=True)
            return

        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("Vous n'avez pas les permissions nécessaires pour utiliser cette commande.", ephemeral=True)
            return

        try:
            await interaction.channel.purge(limit=amount)
            await interaction.response.send_message(f"{amount} messages ont été supprimés.")
        except Exception as e:
            await interaction.response.send_message(f"Une erreur est survenue : {e}")

async def setup(bot):
    await bot.add_cog(ClearCog(bot))
