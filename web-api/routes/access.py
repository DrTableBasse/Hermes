"""Gestion des droits du site par rôle Discord, avec anti-escalade (étape 2, tâche 4).

Règles (§4.1) : sauf le propriétaire du serveur, l'acteur ne modifie que les rôles **strictement
sous** son rôle le plus haut et n'accorde ni ne retire un droit qu'il ne possède pas lui-même.
Les détenteurs d'``admin_role`` y sont soumis (``is_admin`` leur donne seulement tous les droits).
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import database as db
from actor_rank import actor_rank, outranks
from middleware.auth_middleware import get_current_user, require_permission
from permissions import PERMISSIONS
from routes import admin

router = APIRouter(prefix="/admin", tags=["access"])


class AccessUpdate(BaseModel):
    permissions: list[str]


def check_escalation(actor: dict, role_position: int, before: set[str], after: set[str]) -> str | None:
    """Message de refus, ou ``None`` si l'acteur peut passer le rôle de ``before`` à ``after``."""
    if actor["is_owner"]:
        return None
    if not outranks(actor, role_position):
        return "Ce rôle est au niveau du vôtre ou au-dessus : vous ne pouvez pas modifier ses accès"
    lacking = sorted((before ^ after) - set(actor["permissions"]))
    if lacking:
        return "Vous ne pouvez accorder ou retirer que des droits que vous possédez : " + ", ".join(lacking)
    return None


async def _roles() -> list[dict]:
    return (await admin._bot("get", "/discord/roles"))["roles"]


@router.get("/access")
async def get_access(user: dict = Depends(get_current_user)):
    require_permission(user, "permissions.manage")
    actor = await actor_rank(user)
    roles = await _roles()
    grants: dict[str, list[str]] = {}
    for row in await db.fetch(
        "SELECT discord_role_id, permission FROM site_permissions ORDER BY permission"
    ):
        if row["permission"] in PERMISSIONS:
            grants.setdefault(str(row["discord_role_id"]), []).append(row["permission"])
    return {
        "catalog": [{"key": k, "label": v} for k, v in PERMISSIONS.items()],
        "roles": [
            {
                "id": r["id"], "name": r["name"], "color": r["color"],
                "position": r["position"], "managed": r["managed"],
                "permissions": sorted(grants.get(r["id"], [])),
                "editable": outranks(actor, r["position"]),
            }
            for r in roles
        ],
        "actor": actor,
    }


@router.put("/access/{role_id}")
async def put_access(role_id: int, body: AccessUpdate, user: dict = Depends(get_current_user)):
    require_permission(user, "permissions.manage")
    unknown = sorted(set(body.permissions) - set(PERMISSIONS))
    if unknown:
        raise HTTPException(status_code=422, detail="Droits inconnus : " + ", ".join(unknown))
    after = set(body.permissions)

    role = next((r for r in await _roles() if r["id"] == str(role_id)), None)
    if role is None:
        raise HTTPException(status_code=404, detail="Rôle introuvable")

    actor = await actor_rank(user)
    before = {
        row["permission"]
        for row in await db.fetch("SELECT permission FROM site_permissions WHERE discord_role_id = $1", role_id)
    }
    refusal = check_escalation(actor, role["position"], before, after)
    if refusal:
        raise HTTPException(status_code=403, detail=refusal)

    actor_id = int(user["sub"])
    new = sorted(after)
    # Une seule instruction : retrait des absents et ajout des nouveaux, atomiques.
    await db.execute(
        """WITH removed AS (
               DELETE FROM site_permissions
               WHERE discord_role_id = $1 AND NOT (permission = ANY($2::text[]))
           )
           INSERT INTO site_permissions (discord_role_id, permission, granted_by)
           SELECT $1, p, $3 FROM unnest($2::text[]) AS p
           ON CONFLICT DO NOTHING""",
        role_id, new, actor_id,
    )
    await admin._log(
        "update", actor_id, target_id=role_id, target_name=role["name"],
        details={"role": role["name"], "before": sorted(before), "after": new},
    )
    return {"id": str(role_id), "permissions": new}
