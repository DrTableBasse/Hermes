"""Rôles autorisés par commande Hermes (table ``command_permissions``) : cache et contrôle d'accès.

Le contrôle s'applique à toutes les commandes d'application via l'arbre du bot
(``HermesCommandTree.interaction_check``), commandes de jeux dynamiques comprises ;
``administration_only`` le refait pour les commandes réservées aux admins.

Cache : lu au démarrage (``main.on_ready``, après la base), relu par l'API interne
(``POST /command-permissions/reload``). Une relecture en échec garde l'ancien cache :
une commande restreinte le reste. Jamais chargé : comportement d'avant l'étape 6
(commande non admin ouverte, commande admin réservée au rôle admin), avec un
avertissement, et nouvel essai au plus toutes les ``RETRY_S`` secondes.

La liste d'une commande est rangée sous le nom de sa commande racine (``ticket``
pour ``/ticket close``). Un rôle supprimé encore présent en base ne correspond à
aucun membre : il est simplement ignoré.
"""
import asyncio
import logging
import time

import discord
from discord import app_commands

from utils import settings
from utils.command_access import can_use
from utils.database import db_manager
from utils.embed_style import Colors, hermes_embed

logger = logging.getLogger(__name__)

ADMIN_ONLY_ATTR = "__hermes_admin_only__"
DENIED = "🔒 Vous n'avez pas accès à cette commande."
RETRY_S = 30.0

_allowed: dict[str, frozenset[int]] = {}
_loaded = False
_last_attempt = float("-inf")
_lock = asyncio.Lock()


async def reload() -> int:
    """Relit la table ; renvoie le nombre de commandes restreintes. Échec : exception, cache gardé."""
    global _allowed, _loaded
    rows = await db_manager.fetch("SELECT command_name, role_id FROM command_permissions")
    allowed: dict[str, set[int]] = {}
    for row in rows:
        allowed.setdefault(row["command_name"], set()).add(int(row["role_id"]))
    _allowed = {name: frozenset(ids) for name, ids in allowed.items()}
    _loaded = True
    return len(_allowed)


async def ensure_loaded() -> None:
    """Charge le cache s'il ne l'a jamais été (au plus un essai toutes les ``RETRY_S`` s)."""
    global _last_attempt
    if _loaded or time.monotonic() - _last_attempt < RETRY_S:
        return
    async with _lock:
        if _loaded or time.monotonic() - _last_attempt < RETRY_S:
            return
        _last_attempt = time.monotonic()
        try:
            await reload()
        except Exception as e:
            logger.warning("Rôles autorisés des commandes illisibles (%s) : accès d'avant l'étape 6", e)


def is_loaded() -> bool:
    return _loaded


def allowed_roles(command_name: str) -> frozenset[int]:
    return _allowed.get(command_name, frozenset())


def command_key(command) -> str:
    """Nom sous lequel la liste d'une commande est rangée : celui de sa commande racine."""
    root = getattr(command, "root_parent", None) or command
    return root.name


def is_admin_only(command) -> bool:
    return bool(getattr(getattr(command, "callback", None), ADMIN_ONLY_ATTR, False))


def member_allowed(guild, member, command_name: str, admin_only: bool) -> bool:
    """Règle ``can_use`` appliquée à un membre ; hors serveur, seule une commande libre passe."""
    allowed = set(allowed_roles(command_name))
    if guild is None or not hasattr(member, "roles"):
        return not admin_only and not allowed
    role_ids = {r.id for r in member.roles}
    admin_role = settings.get_role(guild, "admin_role")
    return can_use(
        is_owner=guild.owner_id == member.id,
        is_admin_role=admin_role is not None and admin_role.id in role_ids,
        admin_only=admin_only,
        member_role_ids=role_ids,
        allowed_role_ids=allowed,
    )


async def send_denied(interaction: discord.Interaction) -> None:
    """Refus éphémère, sans nommer les rôles autorisés."""
    embed = hermes_embed(description=DENIED, color=Colors.RED)
    try:
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)
    except discord.HTTPException as e:
        logger.warning("Refus de commande non envoyé : %s", e)


async def check_interaction(interaction: discord.Interaction) -> bool:
    command = interaction.command
    if command is None:
        return True
    await ensure_loaded()
    if member_allowed(interaction.guild, interaction.user, command_key(command), is_admin_only(command)):
        return True
    if interaction.type is not discord.InteractionType.autocomplete:
        await send_denied(interaction)
    return False


class HermesCommandTree(app_commands.CommandTree):
    """Arbre du bot : rôles autorisés vérifiés avant toute commande d'application."""

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return await check_interaction(interaction)
