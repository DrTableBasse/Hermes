import discord
from discord import app_commands
from discord.ext import commands
from utils.command_manager import command_enabled
from utils.decorators import administration_only
from utils.logging import log_command
from utils.embed_style import hermes_embed, Colors


class ClearCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="clear", description="Supprimer des messages en masse")
    @administration_only()
    @command_enabled(guild_specific=True)
    @log_command()
    async def clear(self, interaction: discord.Interaction, amount: int):
        if amount < 1 or amount > 100:
            await interaction.response.send_message(
                embed=hermes_embed(description="❌ Entrez un nombre entre **1** et **100**.", color=Colors.RED),
                ephemeral=True,
            )
            return
        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=amount)
        await interaction.followup.send(
            embed=hermes_embed(
                description=f"🗑️ **{len(deleted)}** message{'s' if len(deleted) > 1 else ''} supprimé{'s' if len(deleted) > 1 else ''}.",
                color=Colors.GREEN,
            ),
            ephemeral=True,
        )


async def setup(bot):
    await bot.add_cog(ClearCog(bot))
