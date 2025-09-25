import discord
from discord import app_commands
from discord.ext import commands
from utils.database import voice_manager
from datetime import datetime
from utils.command_manager import command_enabled
from utils.logging import log_command
import logging

logger = logging.getLogger(__name__)

class CheckVoiceCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="check-voice", description="Vérifier le temps vocal d'un utilisateur")
    @command_enabled(guild_specific=True)
    async def check_voice(self, interaction: discord.Interaction, user: discord.Member):
        user_id = interaction.user.id

        try:
            # Utiliser le gestionnaire PostgreSQL
            user_data = await voice_manager.get_user_voice_data(user_id)
            
            if user_data:
                total_time_seconds = user_data['total_time']
                username = user_data['username']

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

        except Exception as e:
            logger.error(f"[check-voice] Erreur lors de l'exécution de la commande check-voice")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(f"[ERROR] Une erreur est survenue lors de la récupération des données pour la commande check-voice", ephemeral=True)
                else:
                    await interaction.followup.send(f"[ERROR] Une erreur est survenue lors de la récupération des données pour la commande check-voice", ephemeral=True)
            except Exception as send_err:
                logger.error(f"[check-voice] Impossible d'envoyer le message d'erreur : {send_err}")

async def setup(bot):
    await bot.add_cog(CheckVoiceCog(bot))
