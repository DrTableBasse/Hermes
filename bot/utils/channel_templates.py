"""Modèles d'accès des salons : surcharges voulues, plan de changements, jeton d'aperçu.

Fonctions pures (ni Discord réel ni base) : le cog et l'API appliquent le résultat.
Types de salon : ``text``, ``voice``, ``forum``, ``announcement``, ``category``.
"""
import hashlib
import json
from dataclasses import dataclass
from typing import Literal

import discord

TEMPLATES = ("public", "role_required", "announcements", "staff")

_VIEW = discord.Permissions(view_channel=True).value
_MANAGE = discord.Permissions(manage_messages=True).value
_TEXT_WRITE = discord.Permissions(
    send_messages=True, create_public_threads=True,
    create_private_threads=True, send_messages_in_threads=True,
).value
_VOICE_WRITE = discord.Permissions(connect=True, speak=True).value
_FORUM_WRITE = discord.Permissions(
    send_messages=True, create_public_threads=True, send_messages_in_threads=True,
).value

# « Écrire » selon le type de salon ; une catégorie transmet texte et vocal à ses salons.
_WRITE = {
    "text": _TEXT_WRITE,
    "announcement": _TEXT_WRITE,
    "voice": _VOICE_WRITE,
    "forum": _FORUM_WRITE,
    "category": _TEXT_WRITE | _VOICE_WRITE,
}


@dataclass(frozen=True)
class Overwrite:
    target_id: int
    target_type: Literal["role", "member"]
    allow: int
    deny: int


def template_overwrites(template: str, everyone_id: int, bot_id: int, roles: list[int],
                        staff_roles: list[int], channel_type: str) -> dict[int, Overwrite]:
    """Surcharges voulues pour ``template`` : ``{target_id: Overwrite}``.

    ``roles`` : rôles R de « Rôle requis » et « Annonces » ; ``staff_roles`` : modèle « Staff ».
    Le bot garde toujours voir/écrire/gérer. « Public » n'écrit aucune surcharge ``@everyone``.
    """
    if template not in TEMPLATES:
        raise ValueError(f"Modèle inconnu : {template!r}")
    if channel_type not in _WRITE:
        raise ValueError(f"Type de salon inconnu : {channel_type!r}")
    write = _WRITE[channel_type]
    manage = 0 if channel_type == "voice" else _MANAGE

    wanted: dict[int, Overwrite] = {}

    def put(target_id: int, kind: str, allow: int, deny: int) -> None:
        old = wanted.get(target_id)
        if old is not None:  # même cible citée deux fois : on cumule
            allow, deny = allow | old.allow, deny | old.deny
        wanted[target_id] = Overwrite(target_id, kind, allow, deny)

    put(bot_id, "member", _VIEW | write | manage, 0)
    if template == "role_required":
        put(everyone_id, "role", 0, _VIEW)
        for r in roles:
            put(r, "role", _VIEW | write, 0)
    elif template == "announcements":
        put(everyone_id, "role", _VIEW, write)
        for r in roles:
            put(r, "role", write, 0)
    elif template == "staff":
        put(everyone_id, "role", 0, _VIEW)
        for r in staff_roles:
            put(r, "role", _VIEW | write | manage, 0)
    return wanted


def _bits(ow: Overwrite | None) -> dict | None:
    return None if ow is None else {"allow": ow.allow, "deny": ow.deny}


def plan(current: dict[int, Overwrite], wanted: dict[int, Overwrite],
         managed_ids: set[int]) -> list[dict]:
    """Changements pour passer de ``current`` à ``wanted``.

    Ne retire que les surcharges de ``managed_ids`` (``@everyone``, bot, rôles de l'ancien et
    du nouveau modèle) ; toute autre surcharge (membres, rôles tiers) est conservée.
    """
    changes: list[dict] = []
    for tid, new in wanted.items():
        old = current.get(tid)
        if old is None:
            action = "add"
        elif (old.allow, old.deny) != (new.allow, new.deny):
            action = "update"
        else:
            continue
        changes.append({"target_id": tid, "target_type": new.target_type, "action": action,
                        "before": _bits(old), "after": _bits(new)})
    for tid, old in current.items():
        if tid in managed_ids and tid not in wanted:
            changes.append({"target_id": tid, "target_type": old.target_type,
                            "action": "remove", "before": _bits(old), "after": None})
    return changes


def preview_token(channel_id: int, current: dict[int, Overwrite]) -> str:
    """Empreinte stable des surcharges actuelles : change dès que l'état du salon change."""
    rows = sorted((o.target_id, o.target_type, o.allow, o.deny) for o in current.values())
    raw = json.dumps([channel_id, rows], separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()[:32]
