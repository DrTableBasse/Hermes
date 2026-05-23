"""Decorators shared across cogs."""
import functools
import os
import discord
from utils.embed_style import hermes_embed, Colors

ADMIN_ROLE_NAME = os.getenv('ADMIN_ROLE_NAME', 'Administration')


def administration_only():
    """Restrict a slash command to members with the Administration role."""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(self, interaction: discord.Interaction, *args, **kwargs):
            if not interaction.guild:
                await interaction.response.send_message(
                    embed=hermes_embed(
                        description="❌ Cette commande n'est disponible que sur un serveur.",
                        color=Colors.RED,
                    ),
                    ephemeral=True,
                )
                return
            role = discord.utils.get(interaction.guild.roles, name=ADMIN_ROLE_NAME)
            if not role or role not in interaction.user.roles:
                await interaction.response.send_message(
                    embed=hermes_embed(
                        description=f"🔒 Vous devez avoir le rôle **{ADMIN_ROLE_NAME}** pour utiliser cette commande.",
                        color=Colors.RED,
                    ),
                    ephemeral=True,
                )
                return
            return await func(self, interaction, *args, **kwargs)
        return wrapper
    return decorator
