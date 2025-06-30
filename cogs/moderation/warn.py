import discord
from discord import app_commands
from discord.ext import commands
import time
from utils.database import warn_manager
import logging
from datetime import datetime
from utils.command_manager import command_enabled
from utils.logging import log_command

logger = logging.getLogger(__name__)

class WarnCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="warn", description="Avertir un utilisateur avec une raison spécifique")
    @command_enabled(guild_specific=True)
    @log_command()
    async def warn(self, interaction: discord.Interaction, user: discord.Member, reason: str = "Aucune raison spécifiée"):
        """Avertit un utilisateur avec une raison spécifique"""
        try:
            # Vérifier si l'utilisateur a la permission de gérer les messages
            if not interaction.user.guild_permissions.manage_messages:
                await interaction.response.send_message(
                    "❌ Vous n'avez pas les permissions nécessaires pour utiliser cette commande.", 
                    ephemeral=True
                )
                return

            # Ajouter l'avertissement via le gestionnaire de base de données
            success = await warn_manager.add_warn(user.id, reason, interaction.user.id)
            
            if not success:
                await interaction.response.send_message(
                    "❌ Une erreur s'est produite lors de l'ajout de l'avertissement.", 
                    ephemeral=True
                )
                return

            # Notification à l'utilisateur et au modérateur
            embed = discord.Embed(
                title="⚠️ Avertissement",
                description=f"{user.mention} a été averti",
                color=discord.Color.orange()
            )
            embed.add_field(name="Raison", value=reason, inline=False)
            embed.add_field(name="Modérateur", value=interaction.user.mention, inline=True)
            embed.add_field(name="Date", value=f"<t:{int(time.time())}:F>", inline=True)
            
            await interaction.response.send_message(embed=embed)
            
            # Notification privée à l'utilisateur (avec gestion d'erreur améliorée)
            try:
                user_embed = discord.Embed(
                    title="⚠️ Avertissement reçu",
                    description=f"Vous avez été averti sur le serveur **{interaction.guild.name}**",
                    color=discord.Color.orange()
                )
                user_embed.add_field(name="Raison", value=reason, inline=False)
                user_embed.add_field(name="Modérateur", value=interaction.user.display_name, inline=True)
                user_embed.add_field(name="Date", value=f"<t:{int(time.time())}:F>", inline=True)
                
                await user.send(embed=user_embed)
            except discord.Forbidden:
                # L'utilisateur a fermé ses DMs ou bloqué le bot
                await interaction.followup.send("⚠️ Impossible d'envoyer un message privé à l'utilisateur (DMs fermés).", ephemeral=True)
            except discord.HTTPException as e:
                # Autre erreur HTTP
                logger.warning(f"Erreur lors de l'envoi du DM à {user.display_name}: {e}")
                await interaction.followup.send("⚠️ Impossible d'envoyer un message privé à l'utilisateur.", ephemeral=True)
            except Exception as e:
                # Erreur inattendue
                logger.error(f"Erreur inattendue lors de l'envoi du DM à {user.display_name}: {e}")
                await interaction.followup.send("⚠️ Erreur lors de l'envoi du message privé.", ephemeral=True)

            # ✅ Logging automatique géré par command_logger.py
            logger.info(f'Avertissement ajouté par {interaction.user.display_name} pour {user.display_name}: {reason}')
            
        except Exception as e:
            logger.error(f'Erreur dans la commande warn: {e}')
            # Vérifier si l'interaction n'a pas déjà été répondue
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ Une erreur s'est produite lors de l'ajout de l'avertissement.", 
                    ephemeral=True
                )
            else:
                # Utiliser followup si l'interaction a déjà été répondue
                await interaction.followup.send(
                    "❌ Une erreur s'est produite lors de l'ajout de l'avertissement.", 
                    ephemeral=True
                )

    @app_commands.command(name="warns", description="Affiche les avertissements d'un utilisateur")
    async def warns(self, interaction: discord.Interaction, user: discord.Member):
        """Affiche les avertissements d'un utilisateur"""
        try:
            # Récupérer les avertissements via le gestionnaire de base de données
            warns = await warn_manager.get_user_warns(user.id)
            warn_count = await warn_manager.get_warn_count(user.id)
            
            if not warns:
                embed = discord.Embed(
                    title=f"📋 Avertissements - {user.display_name}",
                    description="✅ Aucun avertissement",
                    color=discord.Color.green()
                )
                await interaction.response.send_message(embed=embed)
                return
            
            embed = discord.Embed(
                title=f"📋 Avertissements - {user.display_name}",
                description=f"Total: **{warn_count}** avertissement(s)",
                color=discord.Color.red() if warn_count > 2 else discord.Color.orange()
            )
            
            for i, warn in enumerate(warns[:5], 1):  # Limiter à 5 avertissements
                timestamp = f"<t:{warn['create_time']}:F>"
                embed.add_field(
                    name=f"⚠️ Avertissement #{i}",
                    value=f"**Raison:** {warn['reason']}\n**Date:** {timestamp}",
                    inline=False
                )
            
            if warn_count > 5:
                embed.set_footer(text=f"Et {warn_count - 5} autre(s) avertissement(s)...")
            
            await interaction.response.send_message(embed=embed)
            
            # ✅ Logging automatique géré par command_logger.py
            
        except Exception as e:
            logger.error(f'Erreur dans la commande warns: {e}')
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ Une erreur s'est produite lors de la récupération des avertissements.", 
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "❌ Une erreur s'est produite lors de la récupération des avertissements.", 
                    ephemeral=True
                )

    @app_commands.command(name="warncount", description="Affiche le nombre d'avertissements d'un utilisateur")
    async def warn_count(self, interaction: discord.Interaction, user: discord.Member):
        """Affiche le nombre d'avertissements d'un utilisateur"""
        try:
            count = await warn_manager.get_warn_count(user.id)
            
            color = discord.Color.green() if count == 0 else discord.Color.orange() if count <= 2 else discord.Color.red()
            
            embed = discord.Embed(
                title=f"📊 Statistiques - {user.display_name}",
                color=color
            )
            embed.add_field(
                name="Avertissements",
                value=f"{count} avertissement(s)",
                inline=True
            )
            
            # Ajouter des recommandations basées sur le nombre d'avertissements
            if count == 0:
                embed.add_field(name="Statut", value="✅ Exemplaire", inline=True)
            elif count <= 2:
                embed.add_field(name="Statut", value="⚠️ Attention", inline=True)
            else:
                embed.add_field(name="Statut", value="🚨 Problématique", inline=True)
            
            await interaction.response.send_message(embed=embed)
            
            # ✅ Logging automatique géré par command_logger.py
            
        except Exception as e:
            logger.error(f'Erreur dans la commande warn_count: {e}')
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ Une erreur s'est produite lors de la récupération des statistiques.", 
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "❌ Une erreur s'est produite lors de la récupération des statistiques.", 
                    ephemeral=True
                )

async def setup(bot):
    await bot.add_cog(WarnCog(bot))
