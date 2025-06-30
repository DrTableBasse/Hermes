"""
Cog pour la gestion des statuts des commandes
"""

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
import sys
import os
from datetime import datetime
from utils.command_manager import CommandStatusManager, command_enabled
from utils.logging import log_command_usage
import logging

# Ajouter le répertoire parent au path pour les imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

logger = logging.getLogger(__name__)

class CommandManagementCog(commands.Cog):
    """Cog pour gérer les statuts des commandes"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="command-status", description="Affiche le statut de toutes les commandes")
    @command_enabled(guild_specific=True)
    async def command_status(self, interaction: discord.Interaction):
        """Affiche le statut des commandes"""
        # Vérifier les permissions
        if not (isinstance(interaction.user, discord.Member) and interaction.user.guild_permissions.administrator):
            await interaction.response.send_message(
                "❌ Vous devez être administrateur pour utiliser cette commande.", 
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Statut de toutes les commandes
            all_status = await CommandStatusManager.get_all_command_status(interaction.guild_id)
            
            if not all_status:
                embed = discord.Embed(
                    title="Statut des commandes",
                    description="Aucune commande configurée dans la base de données.",
                    color=discord.Color.blue()
                )
            else:
                enabled_commands = [cmd for cmd, status in all_status.items() if status]
                disabled_commands = [cmd for cmd, status in all_status.items() if not status]
                
                embed = discord.Embed(
                    title="Statut des commandes",
                    color=discord.Color.blue()
                )
                
                if enabled_commands:
                    embed.add_field(
                        name=f"✅ Commandes activées ({len(enabled_commands)})",
                        value="\n".join([f"`/{cmd}`" for cmd in sorted(enabled_commands)]) or "Aucune",
                        inline=False
                    )
                
                if disabled_commands:
                    embed.add_field(
                        name=f"❌ Commandes désactivées ({len(disabled_commands)})",
                        value="\n".join([f"`/{cmd}`" for cmd in sorted(disabled_commands)]) or "Aucune",
                        inline=False
                    )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ Erreur lors de la récupération du statut: {str(e)}", 
                ephemeral=True
            )
    
    @app_commands.command(
        name="enable-command",
        description="Activer une commande (admin seulement)"
    )
    @command_enabled(guild_specific=True)
    async def enable_command(self, interaction: discord.Interaction, command_name: str, global_command: bool = False):
        """Active une commande spécifique"""
        # Vérifier les permissions administrateur
        if not hasattr(interaction.user, 'guild_permissions') or not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Vous devez être administrateur pour utiliser cette commande.", ephemeral=True)
            return

        try:
            guild_id = None if global_command else interaction.guild_id
            
            # Activer la commande
            success = await CommandStatusManager.set_command_status(
                command_name, 
                True, 
                guild_id, 
                interaction
            )
            
            if success:
                guild_name = interaction.guild.name if interaction.guild else "serveur"
                scope = "globalement" if global_command else f"sur le serveur {guild_name}"
                await interaction.response.send_message(
                    f"✅ La commande `/{command_name}` a été activée {scope}.",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"❌ Erreur lors de l'activation de la commande `/{command_name}`.",
                    ephemeral=True
                )
                
        except Exception as e:
            logger.error(f"[enable_command] Erreur: {e}")
            await interaction.response.send_message(
                f"❌ Une erreur s'est produite : {e}",
                ephemeral=True
            )
    
    @app_commands.command(
        name="disable-command",
        description="Désactiver une commande (admin seulement)"
    )
    @command_enabled(guild_specific=True)
    async def disable_command(self, interaction: discord.Interaction, command_name: str, global_command: bool = False):
        """Désactive une commande spécifique"""
        # Vérifier les permissions administrateur
        if not hasattr(interaction.user, 'guild_permissions') or not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Vous devez être administrateur pour utiliser cette commande.", ephemeral=True)
            return

        try:
            guild_id = None if global_command else interaction.guild_id
            
            # Désactiver la commande
            success = await CommandStatusManager.set_command_status(
                command_name, 
                False, 
                guild_id, 
                interaction
            )
            
            if success:
                guild_name = interaction.guild.name if interaction.guild else "serveur"
                scope = "globalement" if global_command else f"sur le serveur {guild_name}"
                await interaction.response.send_message(
                    f"❌ La commande `/{command_name}` a été désactivée {scope}.",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"❌ Erreur lors de la désactivation de la commande `/{command_name}`.",
                    ephemeral=True
                )
                
        except Exception as e:
            logger.error(f"[disable_command] Erreur: {e}")
            await interaction.response.send_message(
                f"❌ Une erreur s'est produite : {e}",
                ephemeral=True
            )
    
    @app_commands.command(name="clear-command-cache", description="Vide le cache des statuts de commandes")
    async def clear_command_cache(self, interaction: discord.Interaction):
        """Vide le cache des statuts de commandes"""
        # Vérifier les permissions
        if not (isinstance(interaction.user, discord.Member) and interaction.user.guild_permissions.administrator):
            await interaction.response.send_message(
                "❌ Vous devez être administrateur pour utiliser cette commande.", 
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            await CommandStatusManager.clear_cache()
            
            embed = discord.Embed(
                title="🧹 Cache vidé",
                description="Le cache des statuts de commandes a été vidé avec succès.",
                color=discord.Color.blue()
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ Erreur lors du vidage du cache: {str(e)}", 
                ephemeral=True
            )

    @app_commands.command(
        name="list-commands-status",
        description="Lister le statut de toutes les commandes (admin seulement)"
    )
    @command_enabled(guild_specific=True)
    async def list_commands_status(self, interaction: discord.Interaction, global_commands: bool = False):
        """Liste le statut de toutes les commandes"""
        # Vérifier les permissions administrateur
        if not hasattr(interaction.user, 'guild_permissions') or not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Vous devez être administrateur pour utiliser cette commande.", ephemeral=True)
            return

        try:
            guild_id = None if global_commands else interaction.guild_id
            
            # Récupérer tous les statuts
            command_statuses = await CommandStatusManager.get_all_command_status(guild_id)
            
            if not command_statuses:
                guild_name = interaction.guild.name if interaction.guild else "serveur"
                scope = "globales" if global_commands else f"du serveur {guild_name}"
                await interaction.response.send_message(
                    f"ℹ️ Aucune commande configurée {scope}.",
                    ephemeral=True
                )
                return
            
            # Créer l'embed
            guild_name = interaction.guild.name if interaction.guild else "serveur"
            scope = "Globales" if global_commands else f"Serveur {guild_name}"
            embed = discord.Embed(
                title=f"📋 Statut des Commandes - {scope}",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
            
            # Organiser les commandes par statut
            enabled_commands = []
            disabled_commands = []
            
            for cmd_name, is_enabled in command_statuses.items():
                if is_enabled:
                    enabled_commands.append(f"`/{cmd_name}`")
                else:
                    disabled_commands.append(f"`/{cmd_name}`")
            
            # Ajouter les champs
            if enabled_commands:
                embed.add_field(
                    name="✅ Commandes Activées",
                    value="\n".join(enabled_commands[:10]),  # Limiter à 10 pour éviter les embeds trop longs
                    inline=True
                )
                if len(enabled_commands) > 10:
                    embed.add_field(
                        name="...",
                        value=f"Et {len(enabled_commands) - 10} autres commandes activées",
                        inline=True
                    )
            
            if disabled_commands:
                embed.add_field(
                    name="❌ Commandes Désactivées",
                    value="\n".join(disabled_commands[:10]),
                    inline=True
                )
                if len(disabled_commands) > 10:
                    embed.add_field(
                        name="...",
                        value=f"Et {len(disabled_commands) - 10} autres commandes désactivées",
                        inline=True
                    )
            
            embed.set_footer(text=f"Total: {len(command_statuses)} commandes")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            await log_command_usage(interaction, "list-commands-status")
            
        except Exception as e:
            logger.error(f"[list_commands_status] Erreur: {e}")
            await interaction.response.send_message(
                f"❌ Une erreur s'est produite : {e}",
                ephemeral=True
            )

async def setup(bot):
    """Setup du cog"""
    await bot.add_cog(CommandManagementCog(bot)) 