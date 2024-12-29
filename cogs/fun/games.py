import discord
from discord import app_commands
from discord.ext import commands
import random
from utils.constants import LOG_CHANNEL_NAME
from utils.logging import log_command_usage
import json

class GamesCog(commands.Cog):
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

    @app_commands.command(name="coinflip", description="Faire un pile ou face")
    async def coinflip(self, interaction: discord.Interaction):
        # Vérifier si la commande est activée
        if not await self.is_command_enabled("coinflip"):
            await interaction.response.send_message("La commande /coinflip est actuellement désactivée.", ephemeral=True)
            return
        
        # Log de la commande
        await log_command_usage(
            interaction=interaction,
            command_name="coinflip",
            member=interaction.user,
            reason="Faire un pile ou face",
            log_channel_name=LOG_CHANNEL_NAME
        )

        # Effectuer le tirage
        result = 'pile' if random.randint(0, 1) == 0 else 'face'
        await interaction.response.send_message(f"🪙 Le résultat est {result} !")

async def setup(bot):
    await bot.add_cog(GamesCog(bot))
