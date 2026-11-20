import discord
from discord import app_commands
from discord.ext import commands
from utils import settings
from utils.command_manager import command_enabled
from utils.logging import log_confession
from utils.embed_style import hermes_embed, Colors


class ConfessCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="confess", description="Envoyer une confession anonyme")
    @command_enabled(guild_specific=True)
    async def confess(self, interaction: discord.Interaction, message: str):
        if not settings.get('confession_channel'):
            await interaction.response.send_message(
                embed=hermes_embed(description="❌ Canal de confession non configuré.", color=Colors.RED),
                ephemeral=True,
            )
            return

        channel = await settings.configured_channel(interaction.guild, 'confession_channel')
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
