"""Salons et modèles d'accès : lecture de l'état Discord, aperçu, application (étape 5).

Utilisé par l'API interne (``api.py``) ; les calculs de modèle sont dans ``channel_templates``.
Tout ce qui lit Discord passe par l'API publique de discord.py (``overwrites``,
``permissions_for``) ; l'écriture se fait en un seul ``channel.edit(overwrites=...)`` par salon,
qui reprend toutes les surcharges existantes et ne change que celles du plan.
"""
import hashlib
import json

import discord

from utils.channel_templates import Overwrite, plan, preview_token, template_overwrites

CHANNEL_TYPES = ("text", "voice", "forum", "announcement", "category")

_TYPE_OF = {
    discord.ChannelType.text: "text",
    discord.ChannelType.news: "announcement",
    discord.ChannelType.voice: "voice",
    discord.ChannelType.stage_voice: "voice",
    discord.ChannelType.forum: "forum",
    discord.ChannelType.category: "category",
}


def channel_type(channel) -> str | None:
    """Type au sens des modèles ; ``None`` pour un type non géré (médias, fils…)."""
    return _TYPE_OF.get(getattr(channel, "type", None))


def current_overwrites(guild: discord.Guild, channel) -> dict[int, Overwrite]:
    """Surcharges actuelles du salon, en entiers (cible rôle si l'id est un rôle du serveur)."""
    out: dict[int, Overwrite] = {}
    for target, ow in channel.overwrites.items():
        allow, deny = ow.pair()
        kind = "role" if guild.get_role(target.id) is not None else "member"
        out[target.id] = Overwrite(target.id, kind, allow.value, deny.value)
    return out


def ordered_channels(guild: discord.Guild) -> list:
    """Salons dans l'ordre de Discord : sans catégorie d'abord, puis chaque catégorie et ses salons."""
    key = lambda c: (c.position, c.id)  # noqa: E731
    cats = sorted((c for c in guild.channels if channel_type(c) == "category"), key=key)
    loose = sorted((c for c in guild.channels if channel_type(c) != "category"
                    and getattr(c, "category_id", None) is None), key=key)
    out = list(loose)
    for cat in cats:
        out.append(cat)
        out.extend(sorted((c for c in guild.channels if getattr(c, "category_id", None) == cat.id),
                          key=key))
    return out


def can_view(guild: discord.Guild, member, channel) -> bool:
    """L'acteur voit-il le salon ? Permissions effectives calculées par Discord ; propriétaire exempté."""
    if guild.owner_id == member.id:
        return True
    return bool(channel.permissions_for(member).view_channel)


def targets_of(channel, sync_children: bool) -> list:
    """Le salon, puis (catégorie + ``sync_children``) chacun de ses salons dans l'ordre."""
    if channel_type(channel) == "category" and sync_children:
        return [channel, *sorted(channel.channels, key=lambda c: (c.position, c.id))]
    return [channel]


# Un nom par bit : les noms de discord.py sans alias, sauf ``view_channel`` (nom actuel de Discord,
# alias de ``read_messages`` dans discord.py).
_PREFERRED = {"view_channel"}
_PERM_NAMES: dict[int, str] = {}
for _name, _bit in discord.Permissions.VALID_FLAGS.items():
    _is_alias = isinstance(discord.Permissions.__dict__.get(_name), discord.flags.alias_flag_value)
    if _name in _PREFERRED or (not _is_alias and _bit not in _PERM_NAMES):
        _PERM_NAMES[_bit] = _name


def _perm_names(value: int) -> list[str]:
    return [name for bit, name in sorted(_PERM_NAMES.items()) if value & bit]


def _bits_names(bits: dict | None) -> dict | None:
    if bits is None:
        return None
    return {"allow": _perm_names(bits["allow"]), "deny": _perm_names(bits["deny"])}


def _target_name(guild: discord.Guild, target_id: int, kind: str) -> str:
    if kind == "role":
        role = guild.get_role(target_id)
        if role is not None:
            return "@everyone" if role.is_default() else role.name
    else:
        member = guild.get_member(target_id)
        if member is not None:
            return member.display_name
    return str(target_id)


def channel_plan(guild: discord.Guild, channel, template: str, roles: list[int],
                 staff_roles: list[int], previous_roles: list[int]) -> tuple[dict, list[dict]]:
    """``(current, changes)`` pour un salon. Ids gérés : @everyone, bot, rôles ancien + nouveau modèle."""
    ctype = channel_type(channel)
    if ctype is None:
        raise ValueError(f"Type de salon non géré : {channel.name}")
    everyone_id, bot_id = guild.default_role.id, guild.me.id
    wanted = template_overwrites(template, everyone_id, bot_id, roles, staff_roles, ctype)
    managed = {everyone_id, bot_id, *roles, *previous_roles}
    if template == "staff":
        managed |= set(staff_roles)
    current = current_overwrites(guild, channel)
    return current, plan(current, wanted, managed)


def describe_changes(guild: discord.Guild, changes: list[dict]) -> list[dict]:
    """Changements lisibles : cible nommée, permissions par nom (avant → après)."""
    return [{
        "target_id": str(c["target_id"]), "target_type": c["target_type"],
        "target_name": _target_name(guild, c["target_id"], c["target_type"]),
        "action": c["action"], "before": _bits_names(c["before"]), "after": _bits_names(c["after"]),
    } for c in changes]


def combined_token(parts: list[tuple[int, dict]], params: list) -> str:
    """Jeton d'aperçu de plusieurs salons : état de chacun + paramètres de l'opération."""
    raw = json.dumps([[preview_token(cid, cur) for cid, cur in parts], params],
                     separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def new_overwrites(guild: discord.Guild, channel, changes: list[dict]) -> dict:
    """Surcharges complètes à écrire : celles du salon, plan appliqué (les autres intactes)."""
    result = dict(channel.overwrites)
    by_id = {t.id: t for t in result}
    for c in changes:
        tid = c["target_id"]
        key = by_id.get(tid)
        if key is None:
            key = (guild.get_role(tid) if c["target_type"] == "role" else guild.get_member(tid)) \
                or discord.Object(id=tid, type=discord.Role if c["target_type"] == "role" else discord.Member)
        if c["action"] == "remove":
            result.pop(key, None)
        else:
            result[key] = discord.PermissionOverwrite.from_pair(
                discord.Permissions(c["after"]["allow"]), discord.Permissions(c["after"]["deny"]))
    return result


# ── Mémorisation (table channel_templates, migration 024) ────────────────────

async def load_templates() -> dict[int, dict]:
    from utils.database import db_manager
    rows = await db_manager.fetch(
        "SELECT channel_id, template, roles, applied_by, applied_at FROM channel_templates")
    return {int(r["channel_id"]): r for r in rows}


async def save_template(channel_id: int, template: str, roles: list[int], applied_by: int) -> None:
    from utils.database import db_manager
    await db_manager.execute(
        "INSERT INTO channel_templates (channel_id, template, roles, applied_by, applied_at) "
        "VALUES ($1, $2, $3, $4, NOW()) ON CONFLICT (channel_id) DO UPDATE SET "
        "template = EXCLUDED.template, roles = EXCLUDED.roles, "
        "applied_by = EXCLUDED.applied_by, applied_at = NOW()",
        channel_id, template, list(roles), applied_by)


async def delete_template(channel_id: int) -> None:
    from utils.database import db_manager
    await db_manager.execute("DELETE FROM channel_templates WHERE channel_id = $1", channel_id)
