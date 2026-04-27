import asyncio
import discord
from discord import app_commands
from discord.ext import commands
from utils.command_manager import command_enabled
from utils.decorators import administration_only
from utils.logging import log_command, log_admin_action


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
            await interaction.response.send_message("❌ Hiérarchie insuffisante.", ephemeral=True)
            return

        await interaction.response.defer()
        try:
            await user.ban(reason=reason)
        except discord.Forbidden:
            await interaction.followup.send("❌ Permissions insuffisantes.")
            return

        embed = discord.Embed(title="🔨 Bannissement temporaire", color=discord.Color.dark_red())
        embed.add_field(name="Membre",     value=user.mention,             inline=True)
        embed.add_field(name="Modérateur", value=interaction.user.mention, inline=True)
        embed.add_field(name="Durée",      value=f"{duration} min",        inline=True)
        embed.add_field(name="Raison",     value=reason,                   inline=False)
        await interaction.followup.send(embed=embed)
        await log_admin_action(self.bot, 'tempban', interaction.user, user, reason, f"{duration} min")

        await asyncio.sleep(duration * 60)
        try:
            await interaction.guild.unban(user)
        except Exception:
            pass


async def setup(bot):
    await bot.add_cog(TempBanCog(bot))
