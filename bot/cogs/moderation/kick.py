import discord
from discord import app_commands
from discord.ext import commands
from utils.command_manager import command_enabled
from utils.decorators import administration_only
from utils.logging import log_command, log_admin_action
from utils.embed_style import hermes_embed, moderation_embed, send_sanction_dm, Colors


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
            await interaction.response.send_message(
                embed=hermes_embed(description="❌ Vous ne pouvez pas expulser ce membre (hiérarchie).", color=Colors.RED),
                ephemeral=True,
            )
            return
        await send_sanction_dm(
            user, 'kick', reason,
            guild_name=interaction.guild.name,
            guild_icon_url=interaction.guild.icon.url if interaction.guild.icon else None,
            moderator_name=interaction.user.display_name,
        )
        try:
            await user.kick(reason=reason)
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=hermes_embed(description="❌ Permissions insuffisantes pour expulser ce membre.", color=Colors.RED),
                ephemeral=True,
            )
            return

        embed = moderation_embed('kick', interaction.user, user, reason)
        await interaction.response.send_message(embed=embed)
        await log_admin_action(self.bot, 'kick', interaction.user, user, reason)


async def setup(bot):
    await bot.add_cog(KickCog(bot))
