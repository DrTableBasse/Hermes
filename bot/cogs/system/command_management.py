import discord
from discord import app_commands
from discord.ext import commands
from utils.command_manager import CommandStatusManager
from utils.decorators import administration_only
from utils.embed_style import hermes_embed, Colors


class CommandManagementCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="enable-command", description="Activer une commande")
    @administration_only()
    async def enable_command(self, interaction: discord.Interaction, command_name: str):
        await CommandStatusManager.set(command_name, True, interaction.guild_id,
                                       actor_name=interaction.user.display_name)
        await interaction.response.send_message(
            embed=hermes_embed(description=f"✅ Commande `/{command_name}` activée.", color=Colors.GREEN),
            ephemeral=True,
        )

    @app_commands.command(name="disable-command", description="Désactiver une commande")
    @administration_only()
    async def disable_command(self, interaction: discord.Interaction, command_name: str):
        await CommandStatusManager.set(command_name, False, interaction.guild_id,
                                       actor_name=interaction.user.display_name)
        await interaction.response.send_message(
            embed=hermes_embed(description=f"❌ Commande `/{command_name}` désactivée.", color=Colors.ORANGE),
            ephemeral=True,
        )

    @app_commands.command(name="commands-status", description="Afficher le statut de toutes les commandes")
    @administration_only()
    async def commands_status(self, interaction: discord.Interaction):
        statuses = await CommandStatusManager.get_all(interaction.guild_id)
        if not statuses:
            await interaction.response.send_message(
                embed=hermes_embed(description="Aucune commande enregistrée.", color=Colors.GREY),
                ephemeral=True,
            )
            return

        enabled = [f"✅ `/{k}`" for k, v in sorted(statuses.items()) if v]
        disabled = [f"❌ `/{k}`" for k, v in sorted(statuses.items()) if not v]

        embed = hermes_embed(
            title="⚙️  Statut des commandes",
            color=Colors.BLUE,
        )
        if enabled:
            embed.add_field(name=f"Activées ({len(enabled)})", value="\n".join(enabled), inline=True)
        if disabled:
            embed.add_field(name=f"Désactivées ({len(disabled)})", value="\n".join(disabled), inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(CommandManagementCog(bot))
