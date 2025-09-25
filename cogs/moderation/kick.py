import discord
from discord import app_commands
from discord.ext import commands
import time
from datetime import datetime
import logging
from utils.command_manager import command_enabled
from utils.logging import log_command

logger = logging.getLogger(__name__)

class KickCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="kick", description="Expulser un utilisateur du serveur")
    @command_enabled(guild_specific=True)
    @log_command()
    async def kick(self, interaction: discord.Interaction, user: discord.Member, reason: str = "Aucune raison spécifiée"):
        """Expulse un utilisateur du serveur"""
        try:
            # Vérifier les permissions
            if not interaction.user.guild_permissions.kick_members:
                await interaction.response.send_message("Vous n'avez pas les permissions nécessaires pour utiliser cette commande.", ephemeral=True)
                return

            # Vérifier que l'utilisateur ne peut pas se kick lui-même
            if user == interaction.user:
                await interaction.response.send_message("❌ Vous ne pouvez pas vous expulser vous-même.", ephemeral=True)
                return

            # Vérifier que l'utilisateur ne peut pas kick quelqu'un avec des permissions supérieures
            if user.top_role >= interaction.user.top_role:
                await interaction.response.send_message("❌ Vous ne pouvez pas expulser quelqu'un avec un rôle supérieur ou égal au vôtre.", ephemeral=True)
                return

            # Expulser l'utilisateur
            await user.kick(reason=reason)
            
            # Créer l'embed de confirmation
            embed = discord.Embed(
                title="👢 Utilisateur Expulsé",
                description=f"{user.mention} a été expulsé du serveur",
                color=discord.Color.red(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Modérateur", value=interaction.user.mention, inline=True)
            embed.add_field(name="Raison", value=reason, inline=True)
            embed.add_field(name="Date", value=f"<t:{int(time.time())}:F>", inline=True)
            
            await interaction.response.send_message(embed=embed)
            
            # Notification privée à l'utilisateur (avec gestion d'erreur améliorée)
            try:
                user_embed = discord.Embed(
                    title="👢 Expulsion",
                    description=f"Vous avez été expulsé du serveur **{interaction.guild.name}**",
                    color=discord.Color.red(),
                    timestamp=datetime.now()
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
            logger.info(f'Utilisateur {user.display_name} expulsé par {interaction.user.display_name} pour: {reason}')
            
        except Exception as e:
            logger.error(f'Erreur dans la commande kick')
            # Vérifier si l'interaction n'a pas déjà été répondue
            if not interaction.response.is_done():
                await interaction.response.send_message(f"❌ Une erreur s'est produite lors de l'expulsion de l'utilisateur", ephemeral=True)
            else:
                # Utiliser followup si l'interaction a déjà été répondue
                await interaction.followup.send(f"❌ Une erreur s'est produite lors de l'expulsion de l'utilisateur", ephemeral=True)

async def setup(bot):
    await bot.add_cog(KickCog(bot))
