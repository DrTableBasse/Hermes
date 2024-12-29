import discord
from discord import app_commands
from discord.ext import commands
from utils.constants import cogs_names

class ReloadCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        


    @app_commands.command(name="reload", description="Recharge tous les cogs")
    async def reload(self, interaction: discord.Interaction):

        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("Vous n'avez pas les permissions nécessaires pour utiliser cette commande.", ephemeral=True)
            

        for cog in cogs_names():
            try:
                await self.bot.unload_extension(f'{cog}')
                await self.bot.load_extension(f'{cog}')
                #print(f'Reloaded {cog}')
            except Exception as e:
                print(f'An error occurred while reloading {cog}: {e}')
                await interaction.response.send_message(f"Une erreur est survenue lors du rechargement de {cog}: {e}", ephemeral=True)

        await interaction.response.send_message("Tous les cogs ont été rechargés.")

async def setup(bot):
    await bot.add_cog(ReloadCog(bot))
