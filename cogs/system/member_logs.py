import discord
from discord.ext import commands
from discord import Embed, Colour
from utils.constants import LOG_CHANNEL_ID, WELCOME_CHANNEL_ID
from utils.database import user_message_stats_manager
from discord import app_commands
import logging

logger = logging.getLogger("member_logs")

class MemberLogs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Gère l'événement lorsqu'un membre rejoint le serveur."""
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
    async def on_member_remove(self, member: discord.Member):
        """Gère l'événement lorsqu'un membre quitte le serveur."""
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
            await user_message_stats_manager.increment_message_count(message.author.id, message.channel.id)
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

# Ajout du cog au bot
async def setup(bot):
    await bot.add_cog(MemberLogs(bot))
