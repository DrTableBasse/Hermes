"""Réglages du serveur : lecture/écriture en base, rechargement du bot."""
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import bot_client
import database as db
from middleware.auth_middleware import get_current_user, require_any_permission, require_permission
from settings_registry import G_ROLES, ID_KINDS, SETTINGS, validate

# Listes Discord en lecture seule : lues par la vue d'ensemble, Jeux, Réglages et Accès.
DISCORD_LIST_RIGHTS = ("admin.view", "games.manage", "settings.manage", "permissions.manage")

# Réglages qui désignent un rôle donnant des droits : admin_role (tous les droits du site),
# mod_role/authorized_roles (commandes du bot), rôles que le bot attribue seul (niveaux, bump).
# `settings.manage` seul permettrait d'y nommer son propre rôle, ou un rôle d'admin, et de
# contourner l'anti-escalade : réservés au propriétaire et aux admins (`is_admin`).
ADMIN_ONLY_SETTINGS = frozenset(
    k for k, d in SETTINGS.items() if d.group == G_ROLES or d.kind == "role"
)
ADMIN_ONLY_DETAIL = "Réservé aux administrateurs : ce réglage désigne un rôle qui donne des droits"

# Réglages gardés au registre (copie identique côté bot, amorçage de la migration 021) mais sans
# effet : ni listés ni modifiables. redacteur_role → droits articles.* de la page Accès.
SUPERSEDED_SETTINGS = {"redacteur_role": "Réglage remplacé par la page Accès (/admin/acces)"}

router = APIRouter(tags=["settings"])


class SettingValue(BaseModel):
    value: str


async def _stored_values() -> dict:
    rows = await db.fetch("SELECT key, value FROM bot_settings")
    return {r["key"]: r["value"] for r in rows}


def _effective(key: str, stored: dict) -> str:
    value = stored.get(key)
    if value is None:
        value = SETTINGS[key].default
    return value or ""


def _resolve(kind: str, value: str, channels: Optional[dict], roles: Optional[dict]):
    """``{id, name, exists}`` pour un salon/une catégorie/un rôle, sinon ``None``."""
    if kind not in ID_KINDS or not value.isdigit():
        return None
    known = roles if kind == "role" else channels
    if known is None:  # bot injoignable : on ne sait pas
        return {"id": value, "name": None, "exists": None}
    name = known.get(value)
    return {"id": value, "name": name, "exists": name is not None}


@router.get("/admin/settings")
async def list_settings(user: dict = Depends(get_current_user)):
    require_permission(user, "settings.manage")
    stored = await _stored_values()
    chan_data = await bot_client.bot_get("/discord/channels")
    role_data = await bot_client.bot_get("/discord/roles")
    channels = {str(c["id"]): c["name"] for c in chan_data["channels"]} if chan_data else None
    roles = {str(r["id"]): r["name"] for r in role_data["roles"]} if role_data else None

    groups: dict[str, list] = {}
    for d in SETTINGS.values():
        if d.key in SUPERSEDED_SETTINGS:
            continue
        value = _effective(d.key, stored)
        groups.setdefault(d.group, []).append({
            "key": d.key,
            "label": d.label,
            "kind": d.kind,
            "value": value,
            "can_create": d.channel_name is not None,
            "admin_only": d.key in ADMIN_ONLY_SETTINGS,
            "resolved": _resolve(d.kind, value, channels, roles),
        })
    return {"groups": [{"name": name, "items": items} for name, items in groups.items()]}


@router.put("/admin/settings/{key}")
async def put_setting(key: str, body: SettingValue, user: dict = Depends(get_current_user)):
    require_permission(user, "settings.manage")
    if key not in SETTINGS:
        raise HTTPException(status_code=404, detail="Réglage inconnu")
    if key in ADMIN_ONLY_SETTINGS and not user.get("is_admin"):
        raise HTTPException(status_code=403, detail=ADMIN_ONLY_DETAIL)
    if key in SUPERSEDED_SETTINGS:
        raise HTTPException(status_code=409, detail=SUPERSEDED_SETTINGS[key])
    try:
        value = validate(key, body.value)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if value == "":
        # Valeur vide = réglage effacé : pas de chaîne vide en base, le défaut du registre s'applique.
        await db.execute("DELETE FROM bot_settings WHERE key = $1", key)
    else:
        await db.execute(
            """INSERT INTO bot_settings (key, value, updated_by, updated_at)
               VALUES ($1, $2, $3, NOW())
               ON CONFLICT (key) DO UPDATE
               SET value = EXCLUDED.value, updated_by = EXCLUDED.updated_by, updated_at = NOW()""",
            key, value, int(user["sub"]),
        )
    # Le bot relit la base ; s'il est injoignable, il se resynchronise sous 5 min.
    reloaded = await bot_client.bot_post("/settings/reload") is not None
    return {"key": key, "value": value, "bot_reloaded": reloaded}


@router.post("/admin/settings/{key}/create-channel")
async def create_channel(key: str, user: dict = Depends(get_current_user)):
    require_permission(user, "settings.manage")
    definition = SETTINGS.get(key)
    if definition is None:
        raise HTTPException(status_code=404, detail="Réglage inconnu")
    if definition.channel_name is None:
        raise HTTPException(status_code=422, detail="Ce réglage n'est pas un salon")
    result = await bot_client.bot_post("/settings/ensure-channel", json={"key": key}, timeout=10)
    if result is None:
        raise HTTPException(status_code=502, detail="Le bot n'a pas pu créer le salon")
    return result


@router.get("/admin/discord/channels")
async def discord_channels(user: dict = Depends(get_current_user)):
    require_any_permission(user, *DISCORD_LIST_RIGHTS)
    data = await bot_client.bot_get("/discord/channels")
    if data is None:
        raise HTTPException(status_code=502, detail="Bot injoignable")
    return data


@router.get("/admin/discord/roles")
async def discord_roles(user: dict = Depends(get_current_user)):
    require_any_permission(user, *DISCORD_LIST_RIGHTS)
    data = await bot_client.bot_get("/discord/roles")
    if data is None:
        raise HTTPException(status_code=502, detail="Bot injoignable")
    return data


@router.get("/settings/public")
async def public_settings():
    stored = await _stored_values()
    guild_id = os.getenv("GUILD_ID", "")
    panel_id = _effective("ticket_panel_channel", stored)
    return {
        "invite_url": _effective("invite_url", stored) or None,
        "ticket_panel_url": (
            f"https://discord.com/channels/{guild_id}/{panel_id}"
            if guild_id and panel_id.isdigit() else None
        ),
    }
