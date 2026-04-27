import discord
from datetime import datetime, timezone, timedelta
from discord import app_commands
from discord.ext import commands
from utils.command_manager import command_enabled
from utils.decorators import administration_only
from utils.logging import log_command, log_admin_action


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
        try:
            await user.timeout(until, reason=reason)
        except discord.Forbidden:
            await interaction.response.send_message("❌ Permissions insuffisantes.", ephemeral=True)
            return

        embed = discord.Embed(title="🔇 Mute temporaire", color=discord.Color.greyple())
        embed.add_field(name="Membre",     value=user.mention,             inline=True)
        embed.add_field(name="Modérateur", value=interaction.user.mention, inline=True)
        embed.add_field(name="Durée",      value=f"{duration} min",        inline=True)
        embed.add_field(name="Raison",     value=reason,                   inline=False)
        await interaction.response.send_message(embed=embed)
        await log_admin_action(self.bot, 'tempmute', interaction.user, user, reason, f"{duration} min")


async def setup(bot):
    await bot.add_cog(TempMuteCog(bot))
