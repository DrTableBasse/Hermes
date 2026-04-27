import discord
from discord import app_commands
from discord.ext import commands
from utils.command_manager import CommandStatusManager
from utils.decorators import administration_only


class CommandManagementCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="enable-command", description="Activer une commande")
    @administration_only()
    async def enable_command(self, interaction: discord.Interaction, command_name: str):
        await CommandStatusManager.set(command_name, True, interaction.guild_id)
        await interaction.response.send_message(f"✅ Commande `/{command_name}` activée.", ephemeral=True)

    @app_commands.command(name="disable-command", description="Désactiver une commande")
    @administration_only()
    async def disable_command(self, interaction: discord.Interaction, command_name: str):
        await CommandStatusManager.set(command_name, False, interaction.guild_id)
        await interaction.response.send_message(f"❌ Commande `/{command_name}` désactivée.", ephemeral=True)

    @app_commands.command(name="commands-status", description="Afficher le statut de toutes les commandes")
    @administration_only()
    async def commands_status(self, interaction: discord.Interaction):
        statuses = await CommandStatusManager.get_all(interaction.guild_id)
        if not statuses:
            await interaction.response.send_message("Aucune commande enregistrée.", ephemeral=True)
            return
        lines = [f"{'✅' if v else '❌'} `/{k}`" for k, v in sorted(statuses.items())]
        embed = discord.Embed(title="⚙️ Statut des commandes",
                              description="\n".join(lines), color=discord.Color.blurple())
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(CommandManagementCog(bot))
