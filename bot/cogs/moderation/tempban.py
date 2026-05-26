import asyncio
import discord
from discord import app_commands
from discord.ext import commands
from utils.command_manager import command_enabled
from utils.decorators import administration_only
from utils.logging import log_command, log_admin_action
from utils.embed_style import hermes_embed, moderation_embed, send_sanction_dm, Colors


class TempBanCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="tempban", description="Bannir temporairement un membre")
    @administration_only()
    @command_enabled(guild_specific=True)
    @log_command()
    async def tempban(self, interaction: discord.Interaction, user: discord.Member,
                      duration: int, reason: str = "Aucune raison spécifiée"):
        """duration en minutes"""
        if user.top_role >= interaction.user.top_role:
            await interaction.response.send_message(
                embed=hermes_embed(description="❌ Hiérarchie insuffisante.", color=Colors.RED),
                ephemeral=True,
            )
            return

        await interaction.response.defer()
        await send_sanction_dm(
            user, 'tempban', reason,
            guild_name=interaction.guild.name,
            guild_icon_url=interaction.guild.icon.url if interaction.guild.icon else None,
            moderator_name=interaction.user.display_name,
            duration=f"{duration} min",
        )
        try:
            await user.ban(reason=reason)
        except discord.Forbidden:
            await interaction.followup.send(
                embed=hermes_embed(description="❌ Permissions insuffisantes.", color=Colors.RED),
            )
            return

        embed = moderation_embed('tempban', interaction.user, user, reason, f"{duration} min")
        await interaction.followup.send(embed=embed)
        await log_admin_action(self.bot, 'tempban', interaction.user, user, reason, f"{duration} min")

        await asyncio.sleep(duration * 60)
        try:
            await interaction.guild.unban(user)
        except Exception:
            pass


async def setup(bot):
    await bot.add_cog(TempBanCog(bot))
