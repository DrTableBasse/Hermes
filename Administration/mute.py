import discord
from discord.ext import commands

class Mute(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="mute")
    async def mute(self, ctx, member: discord.Member, *, reason=None):
        muted_role = discord.utils.get(ctx.guild.roles, name="mute")
        await member.add_roles(muted_role)
        await ctx.send(f'{member} a été muté.')

def setup(bot):
    bot.add_cog(Mute(bot))