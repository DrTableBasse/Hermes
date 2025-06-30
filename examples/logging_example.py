"""
Exemple d'utilisation du nouveau système de logging d'Hermes Bot

Ce fichier montre comment implémenter le logging dans différents types de commandes.
"""

import discord
from discord import app_commands
from discord.ext import commands
from utils.logging import log_command_usage, log_admin_action, log_role_assignment
import logging

logger = logging.getLogger(__name__)

class LoggingExampleCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ========================================
    # EXEMPLE 1: Commande Fun (pas d'action admin)
    # ========================================
    @app_commands.command(name="ping", description="Test de latence")
    async def ping(self, interaction: discord.Interaction):
        """Commande fun simple - log d'utilisation seulement"""
        try:
            latency = round(self.bot.latency * 1000)
            embed = discord.Embed(
                title="🏓 Pong!",
                description=f"Latence: **{latency}ms**",
                color=discord.Color.green()
            )
            
            await interaction.response.send_message(embed=embed)
            
            # Log de l'utilisation de la commande
            await log_command_usage(interaction, "ping")
            
        except Exception as e:
            logger.error(f"Erreur dans la commande ping: {e}")
            await interaction.response.send_message("❌ Une erreur s'est produite.", ephemeral=True)

    # ========================================
    # EXEMPLE 2: Commande de Modération
    # ========================================
    @app_commands.command(name="mute", description="Muter un utilisateur")
    async def mute(self, interaction: discord.Interaction, user: discord.Member, duration: str, reason: str = "Aucune raison spécifiée"):
        """Commande de modération - logs d'utilisation ET d'action admin"""
        try:
            # Vérifier les permissions
            if not interaction.user.guild_permissions.manage_roles:
                await interaction.response.send_message("❌ Permissions insuffisantes.", ephemeral=True)
                return

            # Logique de mute (exemple simplifié)
            embed = discord.Embed(
                title="🔇 Utilisateur Muté",
                description=f"{user.mention} a été muté",
                color=discord.Color.purple()
            )
            embed.add_field(name="Durée", value=duration, inline=True)
            embed.add_field(name="Raison", value=reason, inline=True)
            embed.add_field(name="Modérateur", value=interaction.user.mention, inline=True)
            
            await interaction.response.send_message(embed=embed)
            
            # Log de l'utilisation de la commande
            await log_command_usage(interaction, "mute", member=user, reason=reason)
            
            # Log de l'action administrative
            await log_admin_action(interaction, "mute", user, reason=reason, duration=duration)
            
        except Exception as e:
            logger.error(f"Erreur dans la commande mute: {e}")
            await interaction.response.send_message("❌ Une erreur s'est produite.", ephemeral=True)

    # ========================================
    # EXEMPLE 3: Commande d'Attribution de Rôle
    # ========================================
    @app_commands.command(name="addrole", description="Ajouter un rôle à un utilisateur")
    async def add_role(self, interaction: discord.Interaction, user: discord.Member, role: discord.Role):
        """Commande d'attribution de rôle - log spécifique"""
        try:
            # Vérifier les permissions
            if not interaction.user.guild_permissions.manage_roles:
                await interaction.response.send_message("❌ Permissions insuffisantes.", ephemeral=True)
                return

            # Ajouter le rôle
            await user.add_roles(role)
            
            embed = discord.Embed(
                title="✅ Rôle Ajouté",
                description=f"Le rôle {role.mention} a été ajouté à {user.mention}",
                color=discord.Color.green()
            )
            embed.add_field(name="Modérateur", value=interaction.user.mention, inline=True)
            
            await interaction.response.send_message(embed=embed)
            
            # Log de l'utilisation de la commande
            await log_command_usage(interaction, "addrole", member=user)
            
            # Log spécifique d'attribution de rôle
            await log_role_assignment(user, role.name)
            
        except Exception as e:
            logger.error(f"Erreur dans la commande addrole: {e}")
            await interaction.response.send_message("❌ Une erreur s'est produite.", ephemeral=True)

    # ========================================
    # EXEMPLE 4: Commande Système
    # ========================================
    @app_commands.command(name="status", description="Afficher le statut du bot")
    async def status(self, interaction: discord.Interaction):
        """Commande système - log d'utilisation seulement"""
        try:
            embed = discord.Embed(
                title="🤖 Statut du Bot",
                color=discord.Color.blue()
            )
            embed.add_field(name="Latence", value=f"{round(self.bot.latency * 1000)}ms", inline=True)
            embed.add_field(name="Serveurs", value=len(self.bot.guilds), inline=True)
            embed.add_field(name="Utilisateurs", value=len(self.bot.users), inline=True)
            
            await interaction.response.send_message(embed=embed)
            
            # Log de l'utilisation de la commande
            await log_command_usage(interaction, "status")
            
        except Exception as e:
            logger.error(f"Erreur dans la commande status: {e}")
            await interaction.response.send_message("❌ Une erreur s'est produite.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(LoggingExampleCog(bot)) 