import discord
import os
from discord import app_commands
from discord.ext import commands
from utils.command_manager import command_enabled
from utils.logging import log_confession


class ConfessCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="confess", description="Envoyer une confession anonyme")
    @command_enabled(guild_specific=True)
    async def confess(self, interaction: discord.Interaction, message: str):
        channel_id = int(os.getenv('CONFESSION_CHANNEL_ID', '0') or '0')
        if not channel_id:
            await interaction.response.send_message("❌ Canal de confession non configuré.", ephemeral=True)
            return

        channel = interaction.guild.get_channel(channel_id)
        if not channel:
            await interaction.response.send_message("❌ Canal de confession introuvable.", ephemeral=True)
            return

        embed = discord.Embed(
            title="🤫 Confession anonyme",
            description=message,
            color=discord.Color.purple(),
        )
        await channel.send(embed=embed)
        await interaction.response.send_message("✅ Confession envoyée anonymement.", ephemeral=True)
        await log_confession(self.bot, interaction.user.id, message)


async def setup(bot):
    await bot.add_cog(ConfessCog(bot))
