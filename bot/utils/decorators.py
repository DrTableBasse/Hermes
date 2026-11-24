"""Decorators shared across cogs."""
import functools
import discord
from utils import command_permissions
from utils.embed_style import hermes_embed, Colors


def administration_only():
    """Restrict a slash command to the Administration role or to the roles allowed for it.

    Le rôle (réglage ``admin_role``) et les rôles autorisés (``command_permissions``) sont lus
    à chaque appel : un changement fait sur le site s'applique sans redémarrage. Propriétaire
    du serveur : toujours autorisé. Le refus ne nomme aucun rôle.
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
            name = command_permissions.command_key(interaction.command) if interaction.command else func.__name__
            if not command_permissions.member_allowed(interaction.guild, interaction.user, name, admin_only=True):
                await command_permissions.send_denied(interaction)
                return
            return await func(self, interaction, *args, **kwargs)
        setattr(wrapper, command_permissions.ADMIN_ONLY_ATTR, True)
        return wrapper
    return decorator
