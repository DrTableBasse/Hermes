import discord
from discord import app_commands
from discord.ext import commands
from utils.command_manager import command_enabled
from utils.decorators import administration_only
from utils.logging import log_command, log_admin_action


class KickCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="kick", description="Expulser un membre du serveur")
    @administration_only()
    @command_enabled(guild_specific=True)
    @log_command()
    async def kick(self, interaction: discord.Interaction, user: discord.Member,
                   reason: str = "Aucune raison spécifiée"):
        if user.top_role >= interaction.user.top_role:
            await interaction.response.send_message("❌ Vous ne pouvez pas expulser ce membre.", ephemeral=True)
            return
        try:
            await user.kick(reason=reason)
        except discord.Forbidden:
            await interaction.response.send_message("❌ Permissions insuffisantes.", ephemeral=True)
            return

        embed = discord.Embed(title="👢 Expulsion", color=discord.Color.red())
        embed.add_field(name="Membre",     value=user.mention,             inline=True)
        embed.add_field(name="Modérateur", value=interaction.user.mention, inline=True)
        embed.add_field(name="Raison",     value=reason,                   inline=False)
        await interaction.response.send_message(embed=embed)
        await log_admin_action(self.bot, 'kick', interaction.user, user, reason)


async def setup(bot):
    await bot.add_cog(KickCog(bot))
