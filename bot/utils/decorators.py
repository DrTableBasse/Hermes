"""Decorators shared across cogs."""
import functools
import discord
from utils import settings
from utils.embed_style import hermes_embed, Colors


def administration_only():
    """Restrict a slash command to members with the Administration role.

    Le rôle (réglage ``admin_role``) est lu à chaque appel : un changement fait
    sur le site s'applique sans redémarrage.
    """
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
            role = settings.get_role(interaction.guild, 'admin_role')
            if not role or role not in interaction.user.roles:
                role_label = role.name if role else "Administration"
                await interaction.response.send_message(
                    embed=hermes_embed(
                        description=f"🔒 Vous devez avoir le rôle **{role_label}** pour utiliser cette commande.",
                        color=Colors.RED,
                    ),
                    ephemeral=True,
                )
                return
            return await func(self, interaction, *args, **kwargs)
        return wrapper
    return decorator
