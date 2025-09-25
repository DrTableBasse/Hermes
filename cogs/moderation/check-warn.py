import discord
from discord import app_commands
from discord.ext import commands
from utils.database import warn_manager
from datetime import datetime
from utils.command_manager import command_enabled
from utils.logging import log_command
import logging

logger = logging.getLogger(__name__)

class CheckWarnCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="check-warn", description="Vérifier les trois derniers avertissements d'un utilisateur")
    @command_enabled(guild_specific=True)
    async def check_warn(self, interaction: discord.Interaction, user: discord.Member):
        # Vérifier les permissions de l'utilisateur
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("Vous n'avez pas les permissions nécessaires pour utiliser cette commande.", ephemeral=True)
            return

        try:
            # Utiliser le gestionnaire PostgreSQL
            warns = await warn_manager.get_user_warns(user.id)
            
            # Limiter aux 3 derniers avertissements
            warns = warns[:3]

            # If no warns are found
            if not warns:
                await interaction.response.send_message(f"{user.mention} n'a pas d'avertissements.")
                return

            # Create embed
            embed = discord.Embed(
                title=f"Avertissements de {user.display_name}",
                color=discord.Color.orange()
            )

            for i, warn in enumerate(warns, 1):
                # Convert timestamp to readable format
                warn_time = datetime.fromtimestamp(warn['create_time'])
                formatted_time = warn_time.strftime("%d/%m/%Y à %H:%M")
                
                embed.add_field(
                    name=f"Avertissement #{i}",
                    value=f"**Raison:** {warn['reason']}\n**Date:** {formatted_time}",
                    inline=False
                )

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            logger.error(f"[check-warn] Erreur lors de l'exécution de la commande check-warn")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(f"[ERROR] Une erreur est survenue lors de la récupération des avertissements pour la commande check-warn", ephemeral=True)
                else:
                    await interaction.followup.send(f"[ERROR] Une erreur est survenue lors de la récupération des avertissements pour la commande check-warn", ephemeral=True)
            except Exception as send_err:
                logger.error(f"[check-warn] Impossible d'envoyer le message d'erreur : {send_err}")

async def setup(bot):
    await bot.add_cog(CheckWarnCog(bot))
