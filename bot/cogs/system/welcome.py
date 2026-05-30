import logging
import os

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)

WELCOME_CHANNEL_ID = int(os.getenv("WELCOME_CHANNEL_ID", 0))


class WelcomeCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot:
            return

        channel = member.guild.get_channel(WELCOME_CHANNEL_ID)
        if channel is None:
            logger.warning(f"Welcome channel {WELCOME_CHANNEL_ID} not found")
            return

        member_count = member.guild.member_count

        embed = discord.Embed(
            title="🎉 Bienvenue sur le serveur !",
            description=(
                f"Salut {member.mention}, bienvenue chez nous ! 🎊\n"
                "Nous sommes heureux de t'accueillir. "
                "Consulte le règlement et amuse-toi bien !"
            ),
            color=0x2ECC71,
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Nous sommes maintenant {member_count} membres.")

        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            logger.error(f"Missing permissions to send welcome message in channel {WELCOME_CHANNEL_ID}")
        except Exception as e:
            logger.error(f"Failed to send welcome message: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(WelcomeCog(bot))
