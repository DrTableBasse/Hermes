"""Permissions des rôles Discord et accès aux commandes Hermes (étape 6, tâche 3).

Droit du site : ``permissions.manage``.

Permissions Discord d'un rôle — anti-escalade (§4.1), contrôlée ici (403 clair avant tout appel)
puis refaite par le bot (défense en profondeur), avec la même règle (``discord_permissions``) :
- rôle ``managed`` ou non strictement sous le bot : refusé à tous, propriétaire compris (limite
  Discord) ; ``@everyone`` : propriétaire seulement ; sinon rôle strictement sous l'acteur ;
- chaque permission activée ou retirée doit être détenue par l'acteur (permissions effectives du
  serveur, « Administrateur » = toutes) ; activer « Administrateur » : propriétaire seulement, avec
  ``confirm_administrator: true``.

Commandes Hermes — liste blanche par commande racine (``command_permissions``), appliquée par le
bot : l'acteur n'ajoute ou ne retire qu'un rôle strictement sous lui ; la liste d'une commande
réservée aux admins ne se modifie que par un admin du site (``is_admin``).

Toute écriture est journalisée dans ``audit_events`` (kind ``permission``), échecs compris.
"""
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, StringConstraints

import database as db
from actor_rank import actor_rank, outranks
from discord_permissions import (CATALOG_MASK, FAMILIES, LABELS, escalation_error, flags_to_value,
                                 value_to_flags)
from middleware.auth_middleware import get_current_user, require_permission
from routes import admin
from routes.roles import _actor_name, _roles

router = APIRouter(prefix="/admin/permissions", tags=["permissions"])

Snowflake = Annotated[str, StringConstraints(pattern=r"^\d{1,20}$")]
Flag = Annotated[str, StringConstraints(min_length=1, max_length=64)]

ADMIN_COMMAND = "Seul un administrateur du site peut modifier l'accès à une commande réservée aux admins"
ROLE_ABOVE = "Le rôle « {} » est au niveau du vôtre ou au-dessus : vous ne pouvez pas le modifier"
CONFIRM_ADMINISTRATOR = "Activer « Administrateur » demande une confirmation explicite"
DELETED_ROLE = "Rôle supprimé"


class DiscordPermissionsUpdate(BaseModel):
    permissions: list[Flag] = Field(max_length=64)
    confirm_administrator: bool = False


class CommandPermissionsUpdate(BaseModel):
    role_ids: list[Snowflake] = Field(max_length=100)


# ── Outils ──────────────────────────────────────────────────────────────────

async def _call(method: str, path: str, **kwargs) -> dict:
    """``admin._bot`` ; délai et réseau traduits en français, erreurs du bot relayées."""
    try:
        return await admin._bot(method, path, **kwargs)
    except httpx.TimeoutException:
        raise HTTPException(504, "Le bot n'a pas répondu à temps : rechargez la page pour voir l'état actuel")
    except httpx.HTTPError:
        raise HTTPException(503, "Bot injoignable : réessayez dans un instant")


def _role_refusal(role: dict, actor: dict, bot_top: int) -> str | None:
    """Pourquoi l'acteur ne peut pas modifier les permissions de ``role`` (``None`` s'il le peut).

    Même ordre que le bot (``PATCH /discord/roles/{id}/permissions``)."""
    owner = actor["is_owner"]
    if role["is_default"]:
        return None if owner else "Seul le propriétaire du serveur peut modifier les permissions de @everyone"
    if role["managed"]:
        return "Ce rôle est géré par une intégration et ne peut pas être modifié"
    if role["position"] >= bot_top:
        return "Ce rôle n'est pas sous le rôle le plus haut du bot"
    if not owner and role["position"] >= actor["top_position"]:
        return "Ce rôle n'est pas sous votre rôle le plus haut"
    return None


def _editable_flags(role_perms: int, actor: dict) -> list[str]:
    """Drapeaux que l'acteur peut basculer seuls sur ce rôle (même règle que l'enregistrement)."""
    before = role_perms & CATALOG_MASK
    return [flag for _, items in FAMILIES for flag, _, bit in items
            if escalation_error(actor["permissions"], actor["is_owner"], before, before ^ bit) is None]


def _labels(flags) -> list[str]:
    order = [flag for _, items in FAMILIES for flag, _, _ in items]
    return [LABELS[f] for f in order if f in flags]


def _present_role(r: dict, actor: dict, bot_top: int) -> dict:
    """Rôle tel que la page l'affiche : drapeaux du catalogue et ce que l'acteur peut modifier."""
    refusal = _role_refusal(r, actor, bot_top)
    return {
        "id": r["id"], "name": r["name"], "position": r["position"],
        "managed": r["managed"], "is_default": r["is_default"],
        "permissions": sorted(value_to_flags(r["permissions"])),
        "editable": refusal is None,
        "refusal": refusal,
        "editable_flags": _editable_flags(r["permissions"], actor) if refusal is None else [],
    }


async def _discord_state(user: dict) -> dict:
    return await _call("get", "/discord/roles/permissions", params={"actor_id": user["sub"]})


# ── Permissions Discord des rôles ───────────────────────────────────────────

@router.get("/discord")
async def discord_permissions(user: dict = Depends(get_current_user)):
    """Catalogue par famille, rôles (du plus haut au plus bas) avec ce que l'acteur peut modifier."""
    require_permission(user, "permissions.manage")
    state = await _discord_state(user)
    actor, bot_top = state["actor"], state["bot"]["top_position"]
    roles = [_present_role(r, actor, bot_top) for r in state["roles"]]
    return {
        "families": [{"family": fam, "permissions": [{"key": k, "label": label} for k, label, _ in items]}
                     for fam, items in FAMILIES],
        "roles": roles,
        "actor": {"is_owner": actor["is_owner"], "top_position": actor["top_position"],
                  "permissions": sorted(value_to_flags(actor["permissions"])),
                  "is_admin": bool(user.get("is_admin"))},
    }


@router.put("/discord/{role_id}")
async def update_discord_permissions(role_id: int, body: DiscordPermissionsUpdate,
                                     user: dict = Depends(get_current_user)):
    """Remplace les permissions du catalogue d'un rôle (bits hors catalogue conservés par le bot)."""
    require_permission(user, "permissions.manage")
    try:
        after = flags_to_value(body.permissions)
    except ValueError as e:
        raise HTTPException(422, str(e))
    state = await _discord_state(user)
    actor = state["actor"]
    role = next((r for r in state["roles"] if r["id"] == str(role_id)), None)
    if role is None:
        raise HTTPException(404, "Rôle introuvable")
    bot_top = state["bot"]["top_position"]
    refusal = _role_refusal(role, actor, bot_top)
    if refusal:
        raise HTTPException(403, refusal)
    before = role["permissions"] & CATALOG_MASK
    error = escalation_error(actor["permissions"], actor["is_owner"], before, after)
    if error:
        raise HTTPException(403, error)
    added, removed = value_to_flags(after & ~before), value_to_flags(before & ~after)
    if "administrator" in added and not body.confirm_administrator:
        raise HTTPException(422, CONFIRM_ADMINISTRATOR)
    if not added and not removed:
        return {"changed": False, "role": _present_role(role, actor, bot_top)}

    actor_id = int(user["sub"])
    details = {"role": role["name"],
               "before": _labels(value_to_flags(before)), "after": _labels(value_to_flags(after)),
               "added": _labels(added), "removed": _labels(removed)}
    payload = {"actor_id": user["sub"], "actor_name": await _actor_name(user),
               "permissions": after,  # bits du catalogue seuls : le bot conserve les autres
               "confirm_administrator": body.confirm_administrator}
    try:
        result = await _call("patch", f"/discord/roles/{role_id}/permissions", json=payload)
    except HTTPException as e:
        await admin._log("role_permissions_update", actor_id, role_id, {**details, "error": str(e.detail)},
                         success=False, target_name=role["name"])
        raise
    await admin._log("role_permissions_update", actor_id, role_id, details, target_name=role["name"])
    return {"changed": True, "role": _present_role(result["role"], actor, bot_top)}


# ── Accès aux commandes Hermes ──────────────────────────────────────────────

async def _catalog() -> list[dict]:
    return (await _call("get", "/commands/catalog"))["commands"]


async def _allowed() -> dict[str, list[str]]:
    rows = await db.fetch("SELECT command_name, role_id FROM command_permissions ORDER BY command_name, role_id")
    allowed: dict[str, list[str]] = {}
    for row in rows:
        allowed.setdefault(row["command_name"], []).append(str(row["role_id"]))
    return allowed


def _role_names(role_ids, by_id: dict) -> list[str]:
    return [by_id[r]["name"] if r in by_id else f"{DELETED_ROLE} ({r})" for r in role_ids]


@router.get("/commands")
async def command_permissions(user: dict = Depends(get_current_user)):
    """Commandes racines du bot avec leurs rôles autorisés (liste vide : tout le monde, ou les
    admins pour une commande réservée) et les rôles que l'acteur peut ajouter ou retirer."""
    require_permission(user, "permissions.manage")
    catalog = await _catalog()
    allowed = await _allowed()
    roles = await _roles()
    by_id = {r["id"]: r for r in roles}
    actor = await actor_rank(user)
    is_admin = bool(user.get("is_admin"))
    return {
        "commands": [{
            **c,
            "roles": [{"id": rid, "name": by_id[rid]["name"] if rid in by_id else None,
                       "deleted": rid not in by_id} for rid in allowed.get(c["name"], [])],
            "editable": is_admin or not c["admin_only"],
        } for c in catalog],
        "roles": [{"id": r["id"], "name": r["name"], "color": r["color"], "position": r["position"],
                   "assignable": outranks(actor, r["position"])} for r in roles],
        "actor": {"is_owner": actor["is_owner"], "top_position": actor["top_position"], "is_admin": is_admin},
    }


async def _replace_allowed(name: str, role_ids: list[str]) -> None:
    """Remplace toute la liste de la commande en une transaction."""
    async with db.get_conn() as conn:
        async with conn.transaction():
            await conn.execute("DELETE FROM command_permissions WHERE command_name = $1", name)
            if role_ids:
                await conn.executemany(
                    "INSERT INTO command_permissions (command_name, role_id) VALUES ($1, $2)",
                    [(name, int(r)) for r in role_ids],
                )


@router.put("/commands/{name}")
async def update_command_permissions(name: str, body: CommandPermissionsUpdate,
                                     user: dict = Depends(get_current_user)):
    """Remplace la liste blanche d'une commande puis demande au bot de la relire.

    Si la relecture échoue, la liste reste enregistrée (le bot la lira à son prochain démarrage) et
    la réponse porte ``reload_failed: true``."""
    require_permission(user, "permissions.manage")
    command = next((c for c in await _catalog() if c["name"] == name), None)
    if command is None:
        raise HTTPException(404, "Commande introuvable")
    if command["admin_only"] and not user.get("is_admin"):
        raise HTTPException(403, ADMIN_COMMAND)

    new_ids = list(dict.fromkeys(body.role_ids))
    old_ids = (await _allowed()).get(name, [])
    added = [r for r in new_ids if r not in old_ids]
    removed = [r for r in old_ids if r not in new_ids]
    by_id = {r["id"]: r for r in await _roles()}
    actor = await actor_rank(user)
    for rid in added:
        if rid not in by_id:
            raise HTTPException(404, "Rôle introuvable")
    for rid in added + removed:
        role = by_id.get(rid)  # rôle supprimé de Discord : retrait toujours permis (nettoyage)
        if role is not None and not outranks(actor, role["position"]):
            raise HTTPException(403, ROLE_ABOVE.format(role["name"]))
    if not added and not removed:
        # Rien à écrire ni à journaliser, mais le rechargement est relancé : c'est le « Réessayer »
        # d'après un ``reload_failed`` précédent.
        try:
            await _call("post", "/command-permissions/reload")
            reload_failed = False
        except HTTPException:
            reload_failed = True
        return {"command": name, "role_ids": old_ids, "changed": False, "reload_failed": reload_failed}

    actor_id = int(user["sub"])
    details = {"command": name, "before": _role_names(old_ids, by_id), "after": _role_names(new_ids, by_id),
               "added": _role_names(added, by_id), "removed": _role_names(removed, by_id)}
    try:
        await _replace_allowed(name, new_ids)
    except Exception:
        await admin._log("command_permissions_update", actor_id, None,
                         {**details, "error": "Échec de l'enregistrement"}, success=False, target_name=f"/{name}")
        raise HTTPException(500, "Échec de l'enregistrement de la liste : rien n'a été modifié")
    try:
        await _call("post", "/command-permissions/reload")
        reload_failed = False
    except HTTPException:
        reload_failed = True
    await admin._log("command_permissions_update", actor_id, None, {**details, "reload_failed": reload_failed},
                     target_name=f"/{name}")
    return {"command": name, "role_ids": new_ids, "changed": True, "reload_failed": reload_failed}
