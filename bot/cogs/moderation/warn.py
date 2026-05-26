import discord
import time
import logging
from discord import app_commands
from discord.ext import commands
from utils.database import warn_manager
from utils.command_manager import command_enabled
from utils.decorators import administration_only
from utils.logging import log_command, log_admin_action
from utils.embed_style import hermes_embed, moderation_embed, Colors

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
            await interaction.response.send_message(
                embed=hermes_embed(description="❌ Erreur lors de l'ajout de l'avertissement.", color=Colors.RED),
                ephemeral=True,
            )
            return

        embed = moderation_embed('warn', interaction.user, user, reason)
        embed.add_field(name="📅 Date", value=f"<t:{int(time.time())}:F>", inline=False)
        await interaction.response.send_message(embed=embed)

        try:
            dm = hermes_embed(
                title="⚠️  Avertissement reçu",
                description=(
                    f"Vous avez reçu un avertissement sur **{interaction.guild.name}**\n\n"
                    f"**Raison :** {reason}"
                ),
                color=Colors.ORANGE,
                thumbnail_url=interaction.guild.icon.url if interaction.guild.icon else None,
            )
            await user.send(embed=dm)
        except discord.Forbidden:
            pass

        await log_admin_action(self.bot, 'warn', interaction.user, user, reason)

    @app_commands.command(name="warns", description="Afficher les avertissements d'un utilisateur")
    @command_enabled(guild_specific=True)
    async def warns(self, interaction: discord.Interaction, user: discord.Member):
        data = await warn_manager.get_user_warns(user.id)
        count = len(data)

        if not data:
            embed = hermes_embed(
                title=f"📋  Avertissements  ─  {user.display_name}",
                description="✅ Aucun avertissement — casier vierge !",
                color=Colors.GREEN,
                thumbnail_url=user.display_avatar.url,
            )
            await interaction.response.send_message(embed=embed)
            return

        color = Colors.RED if count > 2 else Colors.ORANGE
        embed = hermes_embed(
            title=f"📋  Avertissements  ─  {user.display_name}",
            description=f"**{count}** avertissement{'s' if count > 1 else ''} au total",
            color=color,
            thumbnail_url=user.display_avatar.url,
        )
        for i, w in enumerate(data[:5], 1):
            mod_mention = f"<@{w['moderator_id']}>" if w.get('moderator_id') else "Inconnu"
            embed.add_field(
                name=f"#{i}  ─  <t:{w['create_time']}:R>",
                value=f"**Raison :** {w['reason']}\n**Par :** {mod_mention}",
                inline=False,
            )
        if count > 5:
            embed.set_footer(text=f"…et {count - 5} autre(s)  ·  Hermes · SaucisseLand")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="delwarn", description="Supprimer un avertissement par son ID")
    @administration_only()
    @command_enabled(guild_specific=True)
    async def delwarn(self, interaction: discord.Interaction, warn_id: int):
        w = await warn_manager.get_by_id(warn_id)
        if not w:
            await interaction.response.send_message(
                embed=hermes_embed(description=f"❌ Warn `#{warn_id}` introuvable.", color=Colors.RED),
                ephemeral=True,
            )
            return
        await warn_manager.delete_warn(warn_id)
        await interaction.response.send_message(
            embed=hermes_embed(description=f"✅ Warn `#{warn_id}` supprimé avec succès.", color=Colors.GREEN),
            ephemeral=True,
        )


async def setup(bot):
    await bot.add_cog(WarnCog(bot))
