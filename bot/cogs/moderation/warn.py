import discord
import time
import logging
from discord import app_commands
from discord.ext import commands
from utils.database import warn_manager
from utils.command_manager import command_enabled
from utils.decorators import administration_only
from utils.logging import log_command, log_admin_action

logger = logging.getLogger(__name__)


class WarnCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="warn", description="Avertir un utilisateur")
    @administration_only()
    @command_enabled(guild_specific=True)
    @log_command()
    async def warn(self, interaction: discord.Interaction, user: discord.Member,
                   reason: str = "Aucune raison spécifiée"):
        success = await warn_manager.add_warn(user.id, reason, interaction.user.id)
        if not success:
            await interaction.response.send_message("❌ Erreur lors de l'ajout de l'avertissement.", ephemeral=True)
            return

        embed = discord.Embed(title="⚠️ Avertissement", color=discord.Color.orange())
        embed.add_field(name="Utilisateur",  value=user.mention,              inline=True)
        embed.add_field(name="Modérateur",   value=interaction.user.mention,  inline=True)
        embed.add_field(name="Raison",       value=reason,                    inline=False)
        embed.add_field(name="Date",         value=f"<t:{int(time.time())}:F>", inline=False)
        await interaction.response.send_message(embed=embed)

        try:
            dm = discord.Embed(
                title="⚠️ Vous avez reçu un avertissement",
                description=f"Sur le serveur **{interaction.guild.name}**",
                color=discord.Color.orange(),
            )
            dm.add_field(name="Raison", value=reason, inline=False)
            await user.send(embed=dm)
        except discord.Forbidden:
            pass

        await log_admin_action(self.bot, 'warn', interaction.user, user, reason)

    @app_commands.command(name="warns", description="Afficher les avertissements d'un utilisateur")
    @command_enabled(guild_specific=True)
    async def warns(self, interaction: discord.Interaction, user: discord.Member):
        data  = await warn_manager.get_user_warns(user.id)
        count = len(data)

        if not data:
            embed = discord.Embed(
                title=f"📋 Avertissements — {user.display_name}",
                description="✅ Aucun avertissement",
                color=discord.Color.green(),
            )
            await interaction.response.send_message(embed=embed)
            return

        embed = discord.Embed(
            title=f"📋 Avertissements — {user.display_name}",
            description=f"Total : **{count}**",
            color=discord.Color.red() if count > 2 else discord.Color.orange(),
        )
        for i, w in enumerate(data[:5], 1):
            embed.add_field(
                name=f"⚠️ #{i}",
                value=f"**Raison :** {w['reason']}\n**Date :** <t:{w['create_time']}:F>",
                inline=False,
            )
        if count > 5:
            embed.set_footer(text=f"…et {count - 5} autre(s)")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="delwarn", description="Supprimer un avertissement par son ID")
    @administration_only()
    @command_enabled(guild_specific=True)
    async def delwarn(self, interaction: discord.Interaction, warn_id: int):
        w = await warn_manager.get_by_id(warn_id)
        if not w:
            await interaction.response.send_message(f"❌ Warn #{warn_id} introuvable.", ephemeral=True)
            return
        await warn_manager.delete_warn(warn_id)
        await interaction.response.send_message(f"✅ Warn #{warn_id} supprimé.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(WarnCog(bot))
