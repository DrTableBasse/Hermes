import discord
from discord import app_commands
from discord.ext import commands
import json
import os
from config import LOG_CHANNEL_ID
from utils.logging import log_command_disabled_attempt, log_command
from blagues_api import BlaguesAPI
from utils.command_manager import command_enabled
import logging
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

logger = logging.getLogger("fun_commands")

class BlaguesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Récupérer le token depuis les variables d'environnement
        blagues_token = os.getenv('BLAGUES_API_TOKEN')
        if blagues_token:
            self.blagues = BlaguesAPI(blagues_token)
        else:
            self.blagues = None
            logger.error("❌ BLAGUES_API_TOKEN non configuré dans .env")

    @app_commands.command(name="blague", description="Dit une blague aléatoire")
    @command_enabled(guild_specific=True)
    @log_command()
    async def blague(self, interaction: discord.Interaction):
        try:
            if self.blagues is None:
                await interaction.response.send_message("❌ API de blagues non configurée.", ephemeral=True)
                return
                
            # Assurez-vous que 'random' est une coroutine
            blague = await self.blagues.random()
            # Envoie de la blague
            await interaction.response.send_message(f'{blague.joke}')
            # Envoie de la réponse en spoiler
            await interaction.followup.send(f'||{blague.answer}||')
        except Exception as e:
            logger.error(f"[blague] Erreur lors de l'exécution: {e}")
            # Envoi d'un message d'erreur en cas d'exception
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(f"Une erreur est survenue lors de l'envoi de la blague", ephemeral=True)
                else:
                    await interaction.followup.send(f"Une erreur est survenue lors de l'envoi de la blague", ephemeral=True)
            except Exception as send_err:
                logger.error(f"[blague] Impossible d'envoyer le message d'erreur : {send_err}")

async def setup(bot):
    await bot.add_cog(BlaguesCog(bot))

