import discord
from datetime import datetime, timezone, timedelta
from discord import app_commands
from discord.ext import commands
from utils.command_manager import command_enabled
from utils.decorators import administration_only
from utils.logging import log_command, log_admin_action
from utils.embed_style import hermes_embed, moderation_embed, send_sanction_dm, Colors


class TempMuteCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="tempmute", description="Rendre muet temporairement un membre (timeout)")
    @administration_only()
    @command_enabled(guild_specific=True)
    @log_command()
    async def tempmute(self, interaction: discord.Interaction, user: discord.Member,
                       duration: int, reason: str = "Aucune raison spécifiée"):
        """duration en minutes"""
        until = datetime.now(timezone.utc) + timedelta(minutes=duration)
        await send_sanction_dm(
            user, 'tempmute', reason,
            guild_name=interaction.guild.name,
            guild_icon_url=interaction.guild.icon.url if interaction.guild.icon else None,
            moderator_name=interaction.user.display_name,
            duration=f"{duration} min",
        )
        try:
            await user.timeout(until, reason=reason)
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=hermes_embed(description="❌ Permissions insuffisantes.", color=Colors.RED),
                ephemeral=True,
            )
            return

        embed = moderation_embed('tempmute', interaction.user, user, reason, f"{duration} min")
        await interaction.response.send_message(embed=embed)
        await log_admin_action(self.bot, 'tempmute', interaction.user, user, reason, f"{duration} min")


async def setup(bot):
    await bot.add_cog(TempMuteCog(bot))
