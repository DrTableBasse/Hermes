"""Salons Discord et modèles d'accès (étape 5, tâche 3).

Droit du site : ``channels.manage``. Le modèle « staff » et la resynchronisation des salons
« staff » (après un changement de ``staff_roles``) sont réservés aux admins (``is_admin``).

Anti-escalade (§4.1), sauf propriétaire du serveur :
- tout rôle R cité par un modèle doit être **strictement sous** le rôle le plus haut de l'acteur
  (rang de l'étape 2, ``actor_rank``/``outranks``) — vérifié ici avant tout appel d'écriture ;
- l'acteur doit voir le salon et ne touche pas à la surcharge d'un rôle au-dessus de lui :
  calculé par le bot (permissions effectives), dont les 403 sont relayés tels quels.

L'identifiant Discord de l'acteur (``user["sub"]``) est toujours transmis au bot. Toute écriture
est journalisée dans ``audit_events`` (kinds ``channel`` et ``permission``), échecs compris.
"""
import hmac
from typing import Annotated, Literal, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, StringConstraints

from actor_rank import actor_rank, outranks
from middleware.auth_middleware import get_current_user, require_permission
from routes import admin, settings
from routes.roles import _actor_name, _roles

router = APIRouter(prefix="/admin", tags=["channels"])

# Délais vers le bot. L'application d'un modèle enchaîne au pire rang (10 s) + rôles (10 s)
# + aperçu (5 s) + application (40 s) = 65 s : sous les 70 s du proxy Next (GAMES_TIMEOUT_MS).
BOT_TIMEOUT = 10.0
PREVIEW_TIMEOUT = 5.0
APPLY_TIMEOUT = 40.0

STALE_PREVIEW = "L'aperçu n'est plus à jour : relancez l'aperçu avant d'appliquer"
STAFF_ADMIN_ONLY = "Le modèle « Staff » et sa resynchronisation sont réservés aux administrateurs"
ROLE_ABOVE = "Le rôle « {} » est au niveau du vôtre ou au-dessus : vous ne pouvez pas l'utiliser dans un modèle"

ChannelName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Snowflake = Annotated[str, StringConstraints(pattern=r"^\d{1,20}$")]
ChannelType = Literal["text", "voice", "forum", "announcement", "category"]
TemplateName = Literal["public", "role_required", "announcements", "staff"]
Token = Annotated[str, StringConstraints(min_length=1, max_length=64)]


class ChannelCreate(BaseModel):
    name: ChannelName
    type: ChannelType
    parent_id: Optional[Snowflake] = None


class ChannelUpdate(BaseModel):
    name: Optional[ChannelName] = None
    parent_id: Optional[Snowflake] = None  # présent à null : sortir de la catégorie ; absent : inchangé
    position: Optional[Annotated[int, Field(ge=0)]] = None


class ChannelDelete(BaseModel):
    confirm_name: str


class TemplatePreview(BaseModel):
    template: TemplateName
    roles: list[Snowflake] = Field(default_factory=list, max_length=25)
    sync_children: bool = False


class TemplateApply(TemplatePreview):
    token: Token


class StaffResyncApply(BaseModel):
    token: Token


# ── Outils ──────────────────────────────────────────────────────────────────

async def _call(method: str, path: str, *, timeout: float = BOT_TIMEOUT, **kwargs) -> dict:
    """``admin._bot`` ; délai et réseau traduits en français (504 / 503), erreurs du bot relayées."""
    try:
        return await admin._bot(method, path, timeout=timeout, **kwargs)
    except httpx.TimeoutException:
        raise HTTPException(504, "Le bot n'a pas répondu à temps : l'action se termine peut-être encore. "
                                 "Rechargez la page pour voir l'état des salons.")
    except httpx.HTTPError:
        raise HTTPException(503, "Bot injoignable : réessayez dans un instant")


async def _tree(user: dict) -> dict:
    return await _call("get", "/discord/channels/tree", params={"actor_id": user["sub"]})


async def _channel(user: dict, channel_id: int) -> dict:
    channel = next((c for c in (await _tree(user))["channels"] if c["id"] == str(channel_id)), None)
    if channel is None:
        raise HTTPException(404, "Salon introuvable")
    return channel


def _require_admin(user: dict) -> None:
    if not user.get("is_admin"):
        raise HTTPException(403, STAFF_ADMIN_ONLY)


async def _check_template(user: dict, body: TemplatePreview) -> None:
    """Modèle « staff » : admins seulement. Rôles R : existants et strictement sous l'acteur."""
    if body.template == "staff":
        _require_admin(user)
        return
    if not body.roles:
        return
    actor = await actor_rank(user)
    by_id = {r["id"]: r for r in await _roles()}
    for role_id in body.roles:
        role = by_id.get(role_id)
        if role is None:
            raise HTTPException(404, "Rôle introuvable")
        if not outranks(actor, role["position"]):
            raise HTTPException(403, ROLE_ABOVE.format(role["name"]))


def _template_payload(user: dict, body: TemplatePreview) -> dict:
    return {"template": body.template, "roles": list(body.roles),
            "sync_children": body.sync_children, "actor_id": user["sub"]}


async def _write(action: str, user: dict, method: str, path: str, *, details: dict,
                 target_id: int | None = None, target_name: str | None = None, **kwargs) -> dict:
    """Écriture Discord via le bot ; un échec est journalisé (``success=false``) puis relayé."""
    try:
        return await _call(method, path, **kwargs)
    except HTTPException as e:
        await admin._log(action, int(user["sub"]), target_id, {**details, "error": str(e.detail)},
                         success=False, target_name=target_name)
        raise


async def _apply_previewed(action: str, user: dict, token: str, *, preview_path: str, apply_path: str,
                           payload: dict, details: dict, target_id: int | None = None,
                           target_name: str | None = None) -> dict:
    """Applique un aperçu confirmé et journalise les surcharges réellement écrites.

    L'aperçu est recalculé juste avant : jeton différent → 409 sans écriture. Le bot revérifie le
    jeton sous verrou ; à jeton égal, les changements écrits sont exactement ceux de cet aperçu.
    """
    actor_id = int(user["sub"])
    try:
        preview = await _call("post", preview_path, json=payload, timeout=PREVIEW_TIMEOUT)
        if not hmac.compare_digest(str(preview.get("token", "")).encode(), token.encode()):
            raise HTTPException(409, STALE_PREVIEW)
        result = await _call("post", apply_path, timeout=APPLY_TIMEOUT,
                             json={**payload, "token": token, "actor_name": await _actor_name(user)})
    except HTTPException as e:
        await admin._log(action, actor_id, target_id, {**details, "error": str(e.detail)},
                         success=False, target_name=target_name)
        raise
    if target_id is not None:
        target_name = next((c["name"] for c in preview.get("channels", []) if c["id"] == str(target_id)),
                           target_name)
    failed = result.get("failed") or []
    memo_failed = result.get("memo_failed") or []
    failed_ids = {str(f.get("id")) for f in failed}
    logged = {**details, "count": preview.get("count"), "applied": result.get("applied"),
              "changes": [{"id": c["id"], "name": c["name"], "changes": c["changes"]}
                          for c in preview.get("channels", [])
                          if c["changes"] and str(c["id"]) not in failed_ids]}
    if failed:
        logged["failed"] = failed
    if memo_failed:
        logged["memo_failed"] = memo_failed
    await admin._log(action, actor_id, target_id, logged, success=not failed, target_name=target_name)
    return {"applied": result.get("applied"), "failed": failed, "memo_failed": memo_failed}


def _staff_resync_status(channels: list[dict], roles: list[dict], stored: dict) -> dict:
    """Salons mémorisés « staff » dont les rôles diffèrent des ``staff_roles`` actuels.

    Mêmes règles que le bot (``settings.get_roles``) : seuls les identifiants de rôles existants comptent.
    """
    existing = {r["id"] for r in roles}
    staff = {p.strip() for p in settings._effective("staff_roles", stored).split(",")
             if p.strip().isdigit() and p.strip() in existing}
    pending = [c["id"] for c in channels
               if c.get("template") and c["template"]["template"] == "staff"
               and set(c["template"]["roles"]) != staff]
    return {"pending": len(pending), "channel_ids": pending, "staff_roles_set": bool(staff)}


# ── Lecture ─────────────────────────────────────────────────────────────────

@router.get("/channels")
async def list_channels(user: dict = Depends(get_current_user)):
    """Arbre des salons (ordre Discord), rôles utilisables comme R, rang de l'acteur et, pour un
    admin, les salons « staff » à resynchroniser."""
    require_permission(user, "channels.manage")
    tree = await _tree(user)
    actor = await actor_rank(user)
    roles = await _roles()
    is_admin = bool(user.get("is_admin"))
    return {
        "channels": tree["channels"],
        "templates": [t for t in tree["templates"] if is_admin or t != "staff"],
        "roles": [{"id": r["id"], "name": r["name"], "color": r["color"], "position": r["position"],
                   "managed": r["managed"], "assignable": outranks(actor, r["position"])} for r in roles],
        "actor": {**actor, "is_admin": is_admin},
        "staff_resync": (_staff_resync_status(tree["channels"], roles, await settings._stored_values())
                         if is_admin else None),
    }


# ── Salons ──────────────────────────────────────────────────────────────────

@router.post("/channels")
async def create_channel(body: ChannelCreate, user: dict = Depends(get_current_user)):
    require_permission(user, "channels.manage")
    details = body.model_dump()
    result = await _write("channel_create", user, "post", "/discord/channels", details=details,
                          target_name=body.name,
                          json={**details, "actor_name": await _actor_name(user)})
    await admin._log("channel_create", int(user["sub"]), int(result["id"]),
                     {**details, "name": result["name"]}, target_name=result["name"])
    return result


@router.patch("/channels/{channel_id}")
async def update_channel(channel_id: int, body: ChannelUpdate, user: dict = Depends(get_current_user)):
    require_permission(user, "channels.manage")
    changes = body.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(422, "Aucune modification demandée")
    if "name" in changes and changes["name"] is None:
        raise HTTPException(422, "Le nom ne peut pas être vide")
    if "position" in changes and changes["position"] is None:
        raise HTTPException(422, "Position invalide")
    details = {"changes": changes}
    result = await _write("channel_update", user, "patch", f"/discord/channels/{channel_id}",
                          details=details, target_id=channel_id, target_name=str(channel_id),
                          json={**changes, "actor_id": user["sub"], "actor_name": await _actor_name(user)})
    await admin._log("channel_update", int(user["sub"]), channel_id, details, target_name=result["name"])
    return result


@router.delete("/channels/{channel_id}")
async def delete_channel(channel_id: int, body: ChannelDelete, user: dict = Depends(get_current_user)):
    """Suppression confirmée en retapant le nom exact du salon."""
    require_permission(user, "channels.manage")
    channel = await _channel(user, channel_id)
    if body.confirm_name.strip() != channel["name"]:
        raise HTTPException(422, f"Le nom saisi ne correspond pas : retapez « {channel['name']} » pour confirmer")
    details = {"name": channel["name"], "type": channel["type"], "parent_id": channel["parent_id"]}
    result = await _write("channel_delete", user, "delete", f"/discord/channels/{channel_id}",
                          details=details, target_id=channel_id, target_name=channel["name"],
                          json={"actor_id": user["sub"], "actor_name": await _actor_name(user)})
    await admin._log("channel_delete", int(user["sub"]), channel_id, details, target_name=channel["name"])
    return result


# ── Modèles d'accès ─────────────────────────────────────────────────────────

@router.post("/channels/staff-resync/preview")
async def staff_resync_preview(user: dict = Depends(get_current_user)):
    require_permission(user, "channels.manage")
    _require_admin(user)
    return await _call("post", "/discord/channels/staff-resync/preview",
                       json={"actor_id": user["sub"]}, timeout=PREVIEW_TIMEOUT)


@router.post("/channels/staff-resync/apply")
async def staff_resync_apply(body: StaffResyncApply, user: dict = Depends(get_current_user)):
    require_permission(user, "channels.manage")
    _require_admin(user)
    return await _apply_previewed(
        "channel_staff_resync", user, body.token,
        preview_path="/discord/channels/staff-resync/preview",
        apply_path="/discord/channels/staff-resync/apply",
        payload={"actor_id": user["sub"]}, details={"template": "staff"},
    )


@router.post("/channels/{channel_id}/template/preview")
async def template_preview(channel_id: int, body: TemplatePreview, user: dict = Depends(get_current_user)):
    require_permission(user, "channels.manage")
    await _check_template(user, body)
    return await _call("post", f"/discord/channels/{channel_id}/template/preview",
                       json=_template_payload(user, body), timeout=PREVIEW_TIMEOUT)


@router.post("/channels/{channel_id}/template/apply")
async def template_apply(channel_id: int, body: TemplateApply, user: dict = Depends(get_current_user)):
    """Applique le modèle prévisualisé ; 409 « l'aperçu n'est plus à jour » si l'état a changé."""
    require_permission(user, "channels.manage")
    await _check_template(user, body)
    return await _apply_previewed(
        "channel_template_apply", user, body.token,
        preview_path=f"/discord/channels/{channel_id}/template/preview",
        apply_path=f"/discord/channels/{channel_id}/template/apply",
        payload=_template_payload(user, body),
        details={"template": body.template, "roles": list(body.roles), "sync_children": body.sync_children},
        target_id=channel_id, target_name=str(channel_id),
    )
