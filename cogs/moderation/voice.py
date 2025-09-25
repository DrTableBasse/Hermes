import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timezone
import os
from config import VOICE_LOG_CHANNEL_ID
from utils.logging import log_voice_event, log_command
from utils.database import voice_manager
import logging
from utils.command_manager import command_enabled

logger = logging.getLogger(__name__)

ROLE_NAME = 'Batman'  # Replace with the actual role name

class VoiceLoggingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.voice_state = {}  # Dictionary to keep track of members' join times

    async def _update_user_time(self, user_id: int, time_spent: int):
        """Met à jour le temps vocal d'un utilisateur de manière asynchrone"""
        try:
            # Récupérer le nom d'utilisateur
            user = await self.bot.fetch_user(user_id)
            username = user.display_name or user.name
            
            # Utiliser le gestionnaire de base de données PostgreSQL
            success = await voice_manager.update_user_voice_time(user_id, username, time_spent)
            
            if success:
                logger.info(f'Temps vocal mis à jour pour {username} ({user_id}): +{time_spent}s')
            else:
                logger.error(f'Échec de la mise à jour du temps vocal pour {user_id}')
                
        except discord.NotFound:
            logger.warning(f'Utilisateur {user_id} non trouvé lors de la mise à jour du temps vocal')
        except Exception as e:
            logger.error(f'Erreur lors de la mise à jour du temps vocal pour {user_id}')

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Gère les événements de changement d'état vocal"""
        try:
            # Ignorer les bots
            if member.bot:
                return

            current_time = datetime.now(timezone.utc)
            
            # Membre rejoint un canal vocal
            if before.channel is None and after.channel is not None:
                self.voice_state[member.id] = current_time
                logger.info(f'{member.display_name} a rejoint {after.channel.name}')
                
                # Log l'événement
                await log_voice_event(
                    self.bot,
                    "voice_join",
                    member.id,
                    f"Rejoint {after.channel.name}",
                    VOICE_LOG_CHANNEL_ID
                )
            
            # Membre quitte un canal vocal
            elif before.channel is not None and after.channel is None:
                if member.id in self.voice_state:
                    join_time = self.voice_state[member.id]
                    time_spent = int((current_time - join_time).total_seconds())
                    
                    if time_spent > 0:
                        await self._update_user_time(member.id, time_spent)
                    
                    del self.voice_state[member.id]
                    logger.info(f'{member.display_name} a quitté {before.channel.name} (temps: {time_spent}s)')
                    
                    # Log l'événement
                    await log_voice_event(
                        self.bot,
                        "voice_leave",
                        member.id,
                        f"Quitté {before.channel.name} (temps: {time_spent}s)",
                        VOICE_LOG_CHANNEL_ID
                    )
            
            # Membre change de canal vocal
            elif before.channel is not None and after.channel is not None and before.channel != after.channel:
                if member.id in self.voice_state:
                    join_time = self.voice_state[member.id]
                    time_spent = int((current_time - join_time).total_seconds())
                    
                    if time_spent > 0:
                        await self._update_user_time(member.id, time_spent)
                    
                    # Mettre à jour le temps de connexion pour le nouveau canal
                    self.voice_state[member.id] = current_time
                    logger.info(f'{member.display_name} a changé de {before.channel.name} vers {after.channel.name} (temps précédent: {time_spent}s)')
                    
                    # Log l'événement
                    await log_voice_event(
                        self.bot,
                        "voice_move",
                        member.id,
                        f"Déplacé de {before.channel.name} vers {after.channel.name}",
                        VOICE_LOG_CHANNEL_ID
                    )
                    
        except Exception as e:
            logger.error(f'Erreur lors du traitement de l\'événement vocal')

    @commands.command(name="voicetime")
    async def voice_time(self, ctx, member: discord.Member = None):
        """Affiche le temps vocal d'un utilisateur"""
        try:
            target_member = member or ctx.author
            user_data = await voice_manager.get_user_voice_data(target_member.id)
            
            if not user_data:
                await ctx.send(f"❌ Aucune donnée vocale trouvée pour {target_member.display_name}")
                return
            
            total_seconds = user_data['total_time']
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            
            embed = discord.Embed(
                title=f"🎤 Temps Vocal - {target_member.display_name}",
                color=discord.Color.blue()
            )
            embed.add_field(
                name="Temps Total",
                value=f"{hours}h {minutes}m {seconds}s",
                inline=False
            )
            embed.add_field(
                name="Dernière activité",
                value=user_data.get('last_seen', 'Inconnue'),
                inline=True
            )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f'Erreur dans la commande voice_time')
            await ctx.send("❌ Une erreur s'est produite lors de la récupération des données vocales")

    @commands.command(name="voicetop")
    async def voice_top(self, ctx, limit: int = 10):
        """Affiche le classement des utilisateurs par temps vocal"""
        try:
            if limit > 20:
                limit = 20
            elif limit < 1:
                limit = 5
            
            top_users = await voice_manager.get_top_voice_users(limit)
            
            if not top_users:
                await ctx.send("❌ Aucune donnée vocale disponible")
                return
            
            embed = discord.Embed(
                title="🏆 Classement Temps Vocal",
                color=discord.Color.gold()
            )
            
            for i, user_data in enumerate(top_users, 1):
                total_seconds = user_data['total_time']
                hours, remainder = divmod(total_seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                
                embed.add_field(
                    name=f"{medal} {user_data['username']}",
                    value=f"{hours}h {minutes}m {seconds}s",
                    inline=False
                )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f'Erreur dans la commande voice_top')
            await ctx.send("❌ Une erreur s'est produite lors de la récupération du classement")

    @app_commands.command(name="voice", description="Gérer les salons vocaux")
    @command_enabled(guild_specific=True)
    async def voice(self, interaction: discord.Interaction, action: str, user: discord.Member = None):
        try:
            if action.lower() == "time":
                if user is None:
                    user = interaction.user
                
                user_data = await voice_manager.get_user_voice_data(user.id)
                
                if not user_data:
                    await interaction.response.send_message(f"❌ Aucune donnée vocale trouvée pour {user.display_name}", ephemeral=True)
                    return
                
                total_seconds = user_data['total_time']
                hours, remainder = divmod(total_seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                
                embed = discord.Embed(
                    title=f"🎤 Temps Vocal - {user.display_name}",
                    color=discord.Color.blue()
                )
                embed.add_field(
                    name="Temps Total",
                    value=f"{hours}h {minutes}m {seconds}s",
                    inline=False
                )
                embed.add_field(
                    name="Dernière activité",
                    value=user_data.get('last_seen', 'Inconnue'),
                    inline=True
                )
                
                await interaction.response.send_message(embed=embed, ephemeral=True)
                
            elif action.lower() == "top":
                top_users = await voice_manager.get_top_voice_users(10)
                
                if not top_users:
                    await interaction.response.send_message("❌ Aucune donnée vocale disponible", ephemeral=True)
                    return
                
                embed = discord.Embed(
                    title="🏆 Classement Temps Vocal",
                    color=discord.Color.gold()
                )
                
                for i, user_data in enumerate(top_users, 1):
                    total_seconds = user_data['total_time']
                    hours, remainder = divmod(total_seconds, 3600)
                    minutes, seconds = divmod(remainder, 60)
                    
                    medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                    
                    embed.add_field(
                        name=f"{medal} {user_data['username']}",
                        value=f"{hours}h {minutes}m {seconds}s",
                        inline=False
                    )
                
                await interaction.response.send_message(embed=embed, ephemeral=True)
                
            else:
                await interaction.response.send_message("❌ Action non reconnue. Utilisez 'time' ou 'top'.", ephemeral=True)
                
        except Exception as e:
            logger.error(f'Erreur dans la commande voice')
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("❌ Une erreur s'est produite lors de la récupération des données vocales", ephemeral=True)
                else:
                    await interaction.followup.send("❌ Une erreur s'est produite lors de la récupération des données vocales", ephemeral=True)
            except Exception as send_err:
                logger.error(f"[voice] Impossible d'envoyer le message d'erreur : {send_err}")

    @app_commands.command(name="voice-leaderboard", description="Affiche le classement des 10 utilisateurs ayant passé le plus de temps en vocal.")
    async def voice_leaderboard(self, interaction: discord.Interaction):
        """Affiche le classement général des utilisateurs les plus actifs en vocal"""
        try:
            top_users = await voice_manager.get_top_voice_users(10)
            if not top_users:
                embed = discord.Embed(
                    title="🏆 Classement Temps Vocal",
                    description="Aucune donnée disponible pour le moment.",
                    color=discord.Color.orange()
                )
                await interaction.response.send_message(embed=embed)
                return

            embed = discord.Embed(
                title="🏆 Classement Temps Vocal",
                description="Top 10 des utilisateurs ayant passé le plus de temps en vocal :",
                color=discord.Color.purple()
            )

            for i, user_data in enumerate(top_users, 1):
                user_id = user_data['user_id']
                username = user_data.get('username', f"Utilisateur {user_id}")
                total_seconds = user_data['total_time']
                hours, remainder = divmod(total_seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                user = interaction.guild.get_member(user_id)
                user_mention = user.mention if user else f"<@{user_id}>"
                user_name = user.display_name if user else username
                # Emoji podium
                if i == 1:
                    emoji = "🥇"
                elif i == 2:
                    emoji = "🥈"
                elif i == 3:
                    emoji = "🥉"
                else:
                    emoji = f"**{i}.**"
                embed.add_field(
                    name=f"{emoji} {user_name}",
                    value=f"{user_mention}\n**{hours}h {minutes}m {seconds}s**",
                    inline=False
                )
            if interaction.guild.icon:
                embed.set_thumbnail(url=interaction.guild.icon.url)
            embed.set_footer(text=f"Demandé par {interaction.user.display_name}")
            embed.timestamp = discord.utils.utcnow()
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            logger.error(f"Erreur lors de la récupération du leaderboard vocal")
            await interaction.response.send_message(
                "❌ Une erreur est survenue lors de la récupération du classement.",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(VoiceLoggingCog(bot))
