import discord
import os
from discord import app_commands
from discord.ext import commands
from utils.command_manager import command_enabled
from utils.logging import log_confession
from utils.embed_style import hermes_embed, Colors


class ConfessCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="confess", description="Envoyer une confession anonyme")
    @command_enabled(guild_specific=True)
    async def confess(self, interaction: discord.Interaction, message: str):
        channel_id = int(os.getenv('CONFESSION_CHANNEL_ID', '0') or '0')
        if not channel_id:
            await interaction.response.send_message(
                embed=hermes_embed(description="❌ Canal de confession non configuré.", color=Colors.RED),
                ephemeral=True,
            )
            return

        channel = interaction.guild.get_channel(channel_id)
        if not channel:
            await interaction.response.send_message(
                embed=hermes_embed(description="❌ Canal de confession introuvable.", color=Colors.RED),
                ephemeral=True,
            )
            return

        embed = hermes_embed(
            title="🤫  Confession anonyme",
            description=f">>> {message}",
            color=Colors.PURPLE,
            footer_extra="Utilise /confess pour envoyer la tienne",
        )
        await channel.send(embed=embed)
        await interaction.response.send_message(
            embed=hermes_embed(description="✅ Confession envoyée anonymement.", color=Colors.GREEN),
            ephemeral=True,
        )
        await log_confession(self.bot, interaction.user.id, message)


async def setup(bot):
    await bot.add_cog(ConfessCog(bot))
