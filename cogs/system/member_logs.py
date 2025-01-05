import discord
from discord.ext import commands
from discord import Embed, Colour
from utils.constants import LOG_CHANNEL_ID, WELCOME_CHANNEL_ID


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


# Ajout du cog au bot
async def setup(bot):
    await bot.add_cog(MemberLogs(bot))
