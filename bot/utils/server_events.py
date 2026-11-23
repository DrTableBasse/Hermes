"""Journal des évènements du serveur : mise en forme pure (sans Discord ni base)."""
from datetime import datetime
from typing import Optional

import discord

MAX_CONTENT_LEN = 2000
UNAVAILABLE = "[contenu indisponible]"

A = discord.AuditLogAction

# Entrée d'audit → (kind, action) ; le détail est le différentiel avant/après.
_STRUCTURAL = {
    A.role_create: ("role", "create"), A.role_update: ("role", "update"), A.role_delete: ("role", "delete"),
    A.channel_create: ("channel", "create"), A.channel_update: ("channel", "update"),
    A.channel_delete: ("channel", "delete"),
    A.thread_create: ("thread", "create"), A.thread_update: ("thread", "update"),
    A.thread_delete: ("thread", "delete"),
    A.emoji_create: ("emoji", "create"), A.emoji_update: ("emoji", "update"), A.emoji_delete: ("emoji", "delete"),
    A.sticker_create: ("emoji", "create"), A.sticker_update: ("emoji", "update"),
    A.sticker_delete: ("emoji", "delete"),
    A.invite_create: ("invite", "create"), A.invite_delete: ("invite", "delete"),
    A.guild_update: ("server", "update"),
}
_OVERWRITES = {A.overwrite_create, A.overwrite_update, A.overwrite_delete}

# (attribut du VoiceState, action) dans l'ordre de restitution.
_VOICE_FLAGS = (
    ("mute", "server_mute"),
    ("deaf", "server_deafen"),
    ("self_mute", "self_mute"),
    ("self_deaf", "self_deafen"),
)
VOICE_FLAG_ATTRS = {action: attr for attr, action in _VOICE_FLAGS}


def message_snapshot(content: Optional[str], attachments: list, embeds: int) -> dict:
    """Contenu d'un message tel qu'enregistré : texte tronqué, noms des fichiers, nombre d'embeds."""
    if content is None:
        text = UNAVAILABLE
    elif len(content) > MAX_CONTENT_LEN:
        text = content[:MAX_CONTENT_LEN] + "…"
    else:
        text = content
    return {"content": text, "attachments": list(attachments), "embeds": embeds}


def voice_actions(before, after) -> list:
    """Actions vocales entre deux états ; un changement de salon masque le reste."""
    if before.channel != after.channel:
        if before.channel is None:
            return ["join"]
        if after.channel is None:
            return ["leave"]
        return ["move"]
    if after.channel is None:
        return []
    actions = [action for attr, action in _VOICE_FLAGS if bool(getattr(before, attr)) != bool(getattr(after, attr))]
    if bool(before.self_stream) != bool(after.self_stream):
        actions.append("stream_start" if after.self_stream else "stream_stop")
    return actions


def readable(value):
    """Valeur rendue lisible et sérialisable en JSON."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, discord.Colour):
        return f"#{value.value:06X}"
    if isinstance(value, discord.Permissions):
        return sorted(name for name, enabled in value if enabled)
    if isinstance(value, discord.PermissionOverwrite):
        allow, deny = value.pair()
        return {"allow": readable(allow), "deny": readable(deny)}
    if type(value).__name__.startswith("_EnumValue_"):  # membre d'énumération discord.py (tuple nommé)
        return value.name
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, discord.Asset):
        return value.url
    if isinstance(value, (list, tuple, set, frozenset)):
        return [readable(v) for v in value]
    name = getattr(value, "name", None)
    if isinstance(name, str):
        return name
    if getattr(value, "id", None) is not None:
        return str(value.id)
    return str(value)


def diff_details(before: dict, after: dict) -> dict:
    """Champs modifiés seulement, sous la forme {champ: {avant, après}}."""
    changes = {}
    for key in list(before) + [k for k in after if k not in before]:
        old, new = readable(before.get(key)), readable(after.get(key))
        if old != new:
            changes[key] = {"avant": old, "après": new}
    return {"changes": changes}


def _role_events(action: str, roles) -> list:
    return [("member_role", action, {"role": getattr(r, "name", None), "role_id": r.id}) for r in roles or []]


def audit_to_events(action: discord.AuditLogAction, before: dict, after: dict) -> list:
    """(kind, action, details) pour une entrée d'audit hors sanction ; vide si non suivie."""
    if action in _STRUCTURAL:
        kind, verb = _STRUCTURAL[action]
        return [(kind, verb, diff_details(before, after))]
    if action in _OVERWRITES:
        return [("channel", "update", {"permissions": diff_details(before, after)["changes"]})]
    if action == A.member_role_update:
        # discord.py : rôles ajoutés dans `after`, retirés dans `before`.
        return _role_events("add", after.get("roles")) + _role_events("remove", before.get("roles"))
    if action == A.member_update and "nick" in before.keys() | after.keys():
        nick = diff_details({"nick": before.get("nick")}, {"nick": after.get("nick")})
        return [("member", "nickname", nick)] if nick["changes"] else []
    return []
