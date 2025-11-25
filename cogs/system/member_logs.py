import discord
from discord.ext import commands
from discord import Embed, Colour
from config import LOG_CHANNEL_ID, WELCOME_CHANNEL_ID
from utils.database import user_message_stats_manager, voice_manager
from discord import app_commands
import logging

logger = logging.getLogger("member_logs")

class MemberLogs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Gère l'événement lorsqu'un membre rejoint le serveur."""
        print(f"DEBUG: {member} a rejoint le serveur !")
        
        # Synchroniser le membre dans la base de données
        try:
            await voice_manager.sync_member(
                user_id=member.id,
                username=member.name,
                nickname=member.display_name if member.display_name != member.name else None
            )
        except Exception as e:
            logger.warning(f"Impossible de synchroniser le membre {member.id}: {e}")
        
        guild = member.guild
        welcome_channel = guild.get_channel(WELCOME_CHANNEL_ID)
        log_channel = guild.get_channel(LOG_CHANNEL_ID)

        # Message de bienvenue dans le salon spécifique
        if welcome_channel:
            welcome_embed = Embed(
                title="🎉 Bienvenue sur le serveur !",
                description=f"Salut {member.mention}, bienvenue chez nous ! 🎊\n"
                            f"Nous sommes heureux de t'accueillir. Consulte le règlement et amuse-toi bien !",
                color=Colour.green(),
            )
            welcome_embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
            welcome_embed.set_footer(text=f"Nous sommes maintenant {guild.member_count} membres.")
            await welcome_channel.send(embed=welcome_embed)

        # Log du nouvel arrivant dans le salon de logs
        if log_channel:
            log_embed = Embed(
                title="🟢 Nouveau membre",
                description=f"{member.mention} a rejoint le serveur.",
                color=Colour.green(),
            )
            log_embed.add_field(name="Nom d'utilisateur", value=member.name, inline=True)
            log_embed.add_field(name="Compte créé le", value=member.created_at.strftime("%d/%m/%Y"), inline=True)
            log_embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
            log_embed.set_footer(text=f"ID: {member.id}")
            await log_channel.send(embed=log_embed)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """Gère l'événement lorsqu'un membre est mis à jour (changement de pseudo, etc.)."""
        # Synchroniser si le username ou nickname a changé
        if before.name != after.name or before.display_name != after.display_name:
            try:
                await voice_manager.sync_member(
                    user_id=after.id,
                    username=after.name,
                    nickname=after.display_name if after.display_name != after.name else None
                )
                logger.debug(f"Membre mis à jour: {after.name} ({after.id})")
            except Exception as e:
                logger.warning(f"Impossible de mettre à jour le membre {after.id}: {e}")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Gère l'événement lorsqu'un membre quitte le serveur."""
        print(f"DEBUG: {member} a quitté le serveur !")
        guild = member.guild
        welcome_channel = guild.get_channel(WELCOME_CHANNEL_ID)
        log_channel = guild.get_channel(LOG_CHANNEL_ID)

        # Message de bienvenue dans le salon spécifique
        if welcome_channel:
            welcome_embed = Embed(
                title="💔 Un membre nous quitte...",
                description=f"{member.mention} a quitté le serveur. 😢",
                color=Colour.red(),
            )
            welcome_embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
            welcome_embed.set_footer(text=f"Nous sommes maintenant {guild.member_count} membres.")
            await welcome_channel.send(embed=welcome_embed)

        # Log du départ dans le salon de logs
        if log_channel:
            log_embed = Embed(
                title="🔴 Membre parti",
                description=f"{member.mention} a quitté le serveur.",
                color=Colour.red(),
            )
            log_embed.add_field(name="Nom d'utilisateur", value=member.name, inline=True)
            log_embed.add_field(name="Compte créé le", value=member.created_at.strftime("%d/%m/%Y"), inline=True)
            log_embed.add_field(name="Rejoint le", value=member.joined_at.strftime("%d/%m/%Y"), inline=True)
            log_embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
            log_embed.set_footer(text=f"Il reste {guild.member_count} membres. ID: {member.id}")
            await log_channel.send(embed=log_embed)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        try:
            # Incrémenter le compteur de messages
            await user_message_stats_manager.increment_message_count(message.author.id, message.channel.id)
            
            # Mettre à jour le nom d'utilisateur si nécessaire
            try:
                await user_message_stats_manager.update_username(message.author.id, message.author.display_name)
            except Exception as e:
                logger.warning(f"Impossible de mettre à jour le nom d'utilisateur pour {message.author.id}: {e}")
                
        except Exception as e:
            logger.error(f"Erreur lors de l'incrémentation du compteur de messages : {e}")

    @app_commands.command(name="messages-total", description="Affiche le nombre total de messages envoyés par un utilisateur.")
    @app_commands.describe(user="Utilisateur à analyser (optionnel, par défaut soi-même)")
    async def messages_total(self, interaction: discord.Interaction, user: discord.User = None):
        """Affiche le total de messages d'un utilisateur avec un embed joli"""
        user = user or interaction.user
        total = await user_message_stats_manager.get_total_messages(user.id)
        
        embed = Embed(
            title="📊 Statistiques de Messages",
            description=f"Voici les statistiques de messages pour {user.mention}",
            color=Colour.blue()
        )
        
        embed.add_field(
            name="💬 Total de Messages",
            value=f"**{total:,}** messages envoyés",
            inline=False
        )
        
        embed.set_thumbnail(url=user.avatar.url if user.avatar else user.default_avatar.url)
        embed.set_footer(text=f"Demandé par {interaction.user.name}")
        embed.timestamp = discord.utils.utcnow()
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="messages-top", description="Affiche les 3 salons où l'utilisateur est le plus actif.")
    @app_commands.describe(user="Utilisateur à analyser (optionnel, par défaut soi-même)")
    async def messages_top(self, interaction: discord.Interaction, user: discord.User = None):
        """Affiche le top 3 des salons d'un utilisateur avec un embed joli"""
        user = user or interaction.user
        top_channels = await user_message_stats_manager.get_top_channels(user.id, limit=3)
        
        if not top_channels:
            embed = Embed(
                title="📊 Top Salons",
                description=f"Aucune donnée disponible pour {user.mention}",
                color=Colour.orange()
            )
            embed.set_thumbnail(url=user.avatar.url if user.avatar else user.default_avatar.url)
            await interaction.response.send_message(embed=embed)
            return
        
        embed = Embed(
            title="🏆 Top 3 Salons les Plus Actifs",
            description=f"Voici les salons où {user.mention} est le plus actif :",
            color=Colour.gold()
        )
        
        for i, entry in enumerate(top_channels, 1):
            channel = interaction.guild.get_channel(entry['channel_id'])
            channel_name = channel.name if channel else f"Salon inconnu"
            channel_mention = channel.mention if channel else f"<#{entry['channel_id']}>"
            
            embed.add_field(
                name=f"🥇 {i}er - {channel_name}" if i == 1 else f"🥈 {i}ème - {channel_name}" if i == 2 else f"🥉 {i}ème - {channel_name}",
                value=f"{channel_mention}\n**{entry['message_count']:,}** messages",
                inline=False
            )
        
        embed.set_thumbnail(url=user.avatar.url if user.avatar else user.default_avatar.url)
        embed.set_footer(text=f"Demandé par {interaction.user.name}")
        embed.timestamp = discord.utils.utcnow()
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="messages-leaderboard", description="Affiche le classement des 10 utilisateurs les plus actifs du serveur.")
    async def messages_leaderboard(self, interaction: discord.Interaction):
        """Affiche le classement général des utilisateurs les plus actifs"""
        try:
            # Récupérer le top 10 des utilisateurs
            top_users = await user_message_stats_manager.get_leaderboard(limit=10)
            
            if not top_users:
                embed = Embed(
                    title="🏆 Classement des Messages",
                    description="Aucune donnée disponible pour le moment.",
                    color=Colour.orange()
                )
                await interaction.response.send_message(embed=embed)
                return
            
            embed = Embed(
                title="🏆 Classement des Messages",
                description="Top 10 des utilisateurs les plus actifs du serveur :",
                color=Colour.purple()
            )
            
            for i, entry in enumerate(top_users, 1):
                user_id = entry['user_id']
                total_messages = entry['total_messages']
                
                # Récupérer l'utilisateur
                user = interaction.guild.get_member(user_id)
                user_mention = user.mention if user else f"<@{user_id}>"
                user_name = user.display_name if user else f"Utilisateur {user_id}"
                
                # Emoji pour le podium
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
                    value=f"{user_mention}\n**{total_messages:,}** messages",
                    inline=False
                )
            
            embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)
            embed.set_footer(text=f"Demandé par {interaction.user.name}")
            embed.timestamp = discord.utils.utcnow()
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération du leaderboard : {e}")
            await interaction.response.send_message(
                "❌ Une erreur est survenue lors de la récupération du classement.",
                ephemeral=True
            )
    
    @app_commands.command(name="sync-members", description="Synchronise tous les membres du serveur dans la base de données.")
    async def sync_members(self, interaction: discord.Interaction):
        """Synchronise tous les membres du serveur dans la base de données"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            guild = interaction.guild
            # Charger tous les membres (même ceux hors ligne) avec chunk
            await guild.chunk(cache=True)
            synced = 0
            failed = 0
            
            # Itérer sur tous les membres maintenant chargés
            for member in guild.members:
                if not member.bot:
                    try:
                        nickname = member.display_name if member.display_name != member.name else None
                        await voice_manager.sync_member(member.id, member.name, nickname)
                        synced += 1
                    except Exception as e:
                        logger.warning(f"Erreur lors de la synchronisation de {member.id}: {e}")
                        failed += 1
            
            embed = Embed(
                title="✅ Synchronisation terminée",
                description=f"Synchronisation des membres du serveur terminée.",
                color=Colour.green()
            )
            embed.add_field(name="✅ Synchronisés", value=f"{synced} membres", inline=True)
            if failed > 0:
                embed.add_field(name="❌ Échecs", value=f"{failed} membres", inline=True)
                embed.color = Colour.orange()
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Erreur lors de la synchronisation des membres: {e}")
            await interaction.followup.send(
                "❌ Une erreur est survenue lors de la synchronisation.",
                ephemeral=True
            )

# Ajout du cog au bot
async def setup(bot):
    await bot.add_cog(MemberLogs(bot))
