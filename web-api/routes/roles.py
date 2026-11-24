"""Rôles Discord, rôles des membres, lots et règles automatiques (étape 3, tâche 4).

Droits : ``roles.manage`` (rôles et règles), ``members.roles`` (donner/retirer des rôles).
Anti-escalade (§4.1) : sauf le propriétaire, l'acteur n'agit que sur un rôle strictement sous
son rôle le plus haut ; jamais un rôle ``managed`` ni un rôle au-dessus du bot (le bot refuse
aussi, ``@everyone`` n'est jamais listé). Toute action est journalisée via ``admin._log``.
Les travaux longs (lots, application d'une règle) sont lancés au bot, qui répond par un
``job_id`` consultable avec ``GET /admin/jobs/{job_id}``.
"""
import logging
from typing import Annotated, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, StringConstraints

import database as db
from actor_rank import actor_rank, outranks
from middleware.auth_middleware import get_current_user, require_any_permission, require_permission
from routes import admin

router = APIRouter(prefix="/admin", tags=["roles"])
logger = logging.getLogger(__name__)

# Même liste fermée que bot/utils/role_rules.CONDITIONS.
CONDITIONS = frozenset({
    "voice_hours", "messages", "level", "grade",
    "achievement", "streak_days", "bumps", "invites",
})

RULE_FIELDS = ("condition_type", "condition_value", "role_id", "create_role_name", "create_role_color",
               "remove_when_lost", "exclusive_group", "active", "reconcile")

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Color = Annotated[int, Field(ge=0, le=0xFFFFFF)]
Snowflake = Annotated[str, StringConstraints(pattern=r"^\d{1,20}$")]
Group = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]


class RoleCreate(BaseModel):
    name: Name
    color: Color = 0
    hoist: bool = False
    mentionable: bool = False


class RoleUpdate(BaseModel):
    name: Optional[Name] = None
    color: Optional[Color] = None
    hoist: Optional[bool] = None
    mentionable: Optional[bool] = None
    position: Optional[Annotated[int, Field(ge=1)]] = None


class RoleDelete(BaseModel):
    confirm_members: int


class BulkRoles(BaseModel):
    action: Literal["add", "remove"]
    user_ids: Optional[list[str]] = None
    from_role_id: Optional[Snowflake] = None
    confirm_count: int


class RuleCreate(BaseModel):
    condition_type: str
    condition_value: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    role_id: Optional[Snowflake] = None
    create_role_name: Optional[Name] = None
    create_role_color: Optional[Color] = None
    remove_when_lost: bool = False
    exclusive_group: Optional[Group] = None
    active: bool = True
    reconcile: bool = False


class RuleUpdate(BaseModel):
    condition_type: Optional[str] = None
    condition_value: Optional[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1,
                                                               max_length=100)]] = None
    role_id: Optional[Snowflake] = None
    create_role_name: Optional[Name] = None
    create_role_color: Optional[Color] = None
    remove_when_lost: Optional[bool] = None
    exclusive_group: Optional[Group] = None
    active: Optional[bool] = None
    reconcile: Optional[bool] = None
    preview_seen: bool = False  # le site l'envoie après « Voir l'aperçu »


class RuleApply(BaseModel):
    confirm: bool
    remove_previous_role_id: Optional[Snowflake] = None
    confirm_previous_members: Optional[int] = None  # nombre affiché, requis avec remove_previous_role_id


# ── Outils ──────────────────────────────────────────────────────────────────

async def _roles() -> list[dict]:
    return (await admin._bot("get", "/discord/roles"))["roles"]


async def _role(role_id: int | str) -> dict:
    role = next((r for r in await _roles() if r["id"] == str(role_id)), None)
    if role is None:
        raise HTTPException(status_code=404, detail="Rôle introuvable")
    return role


def _role_refusal(actor: dict, role: dict) -> str | None:
    """Pourquoi l'acteur ne peut pas agir sur ``role`` (``None`` s'il le peut)."""
    if role["managed"]:
        return "Ce rôle est géré par une intégration et ne peut pas être modifié"
    if not role["below_bot"]:
        return "Ce rôle n'est pas sous le rôle le plus haut du bot"
    if not outranks(actor, role["position"]):
        return "Ce rôle est au niveau du vôtre ou au-dessus : vous ne pouvez pas le gérer"
    return None


def _require_manageable(actor: dict, role: dict) -> None:
    refusal = _role_refusal(actor, role)
    if refusal:
        raise HTTPException(status_code=403, detail=refusal)


def _require_outranks(actor: dict, position: int) -> None:
    if not outranks(actor, position):
        raise HTTPException(status_code=403,
                            detail="Ce rôle est au niveau du vôtre ou au-dessus : vous ne pouvez pas le gérer")


async def _actor_name(user: dict) -> str:
    """Nom de l'acteur pour la raison d'audit Discord (« via le site par … »)."""
    row = await db.fetchrow(
        "SELECT COALESCE(nickname, username) AS name FROM user_voice_data WHERE user_id = $1",
        int(user["sub"]),
    )
    return (row["name"] if row else None) or str(user["sub"])


async def _bot_write(action: str, actor_id: int, method: str, path: str, payload: dict, *,
                     details: dict, target_id: int | None = None, target_name: str | None = None):
    """Écriture Discord via le bot ; un échec est journalisé (``success=false``) puis relayé."""
    try:
        return await admin._bot(method, path, json=payload)
    except HTTPException as e:
        await admin._log(action, actor_id, target_id, {**details, "error": str(e.detail)},
                         success=False, target_name=target_name)
        raise


# ── Rôles ───────────────────────────────────────────────────────────────────

@router.get("/roles")
async def list_roles(user: dict = Depends(get_current_user)):
    require_any_permission(user, "roles.manage", "members.roles")
    actor = await actor_rank(user)
    return {
        "roles": [{**r, "editable": _role_refusal(actor, r) is None} for r in await _roles()],
        "actor": actor,
    }


@router.post("/roles")
async def create_role(body: RoleCreate, user: dict = Depends(get_current_user)):
    require_permission(user, "roles.manage")
    actor = await actor_rank(user)
    _require_outranks(actor, 1)  # un rôle neuf est créé tout en bas (position 1)
    actor_id = int(user["sub"])
    details = body.model_dump()
    role = await _bot_write("role_create", actor_id, "post", "/discord/roles",
                            {**details, "actor_name": await _actor_name(user)},
                            details=details, target_name=body.name)
    await admin._log("role_create", actor_id, int(role["id"]), details, target_name=role["name"])
    return role


@router.patch("/roles/{role_id}")
async def update_role(role_id: int, body: RoleUpdate, user: dict = Depends(get_current_user)):
    require_permission(user, "roles.manage")
    changes = body.model_dump(exclude_unset=True, exclude_none=True)
    role = await _role(role_id)
    actor = await actor_rank(user)
    _require_manageable(actor, role)
    if "position" in changes:
        _require_outranks(actor, changes["position"])
    actor_id = int(user["sub"])
    details = {"before": {k: role[k] for k in changes if k in role}, "after": changes}
    updated = await _bot_write("role_update", actor_id, "patch", f"/discord/roles/{role_id}",
                               {**changes, "actor_name": await _actor_name(user)},
                               details=details, target_id=role_id, target_name=role["name"])
    await admin._log("role_update", actor_id, role_id, details, target_name=role["name"])
    return updated


@router.delete("/roles/{role_id}")
async def delete_role(role_id: int, body: RoleDelete, user: dict = Depends(get_current_user)):
    require_permission(user, "roles.manage")
    role = await _role(role_id)
    actor = await actor_rank(user)
    _require_manageable(actor, role)
    if body.confirm_members != role["members"]:
        raise HTTPException(
            status_code=409,
            detail=f"Le nombre a changé : ce rôle compte maintenant {role['members']} membre(s). "
                   "Vérifiez puis confirmez à nouveau.",
        )
    actor_id = int(user["sub"])
    details = {"role": role["name"], "members": role["members"]}
    await _bot_write("role_delete", actor_id, "delete", f"/discord/roles/{role_id}",
                     {"actor_name": await _actor_name(user)},
                     details=details, target_id=role_id, target_name=role["name"])
    await admin._log("role_delete", actor_id, role_id, details, target_name=role["name"])
    return {"ok": True}


# ── Rôles d'un membre et lots ───────────────────────────────────────────────

async def _member_role(action: str, method: str, user_id: int, role_id: int, user: dict):
    require_permission(user, "members.roles")
    role = await _role(role_id)
    _require_manageable(await actor_rank(user), role)
    actor_id = int(user["sub"])
    details = {"role_id": str(role_id), "role": role["name"]}
    result = await _bot_write(action, actor_id, method, f"/discord/members/{user_id}/roles/{role_id}",
                              {"actor_name": await _actor_name(user)}, details=details, target_id=user_id)
    await admin._log(action, actor_id, user_id, details)
    return result


@router.post("/members/{user_id}/roles/{role_id}")
async def add_member_role(user_id: int, role_id: int, user: dict = Depends(get_current_user)):
    return await _member_role("member_role_add", "post", user_id, role_id, user)


@router.delete("/members/{user_id}/roles/{role_id}")
async def remove_member_role(user_id: int, role_id: int, user: dict = Depends(get_current_user)):
    return await _member_role("member_role_remove", "delete", user_id, role_id, user)


@router.post("/roles/{role_id}/bulk")
async def bulk_roles(role_id: int, body: BulkRoles, user: dict = Depends(get_current_user)):
    require_permission(user, "members.roles")
    if (body.user_ids is None) == (body.from_role_id is None):
        raise HTTPException(status_code=422,
                            detail="Choisissez soit une liste de membres, soit un rôle source")
    roles = await _roles()
    role = next((r for r in roles if r["id"] == str(role_id)), None)
    if role is None:
        raise HTTPException(status_code=404, detail="Rôle introuvable")
    _require_manageable(await actor_rank(user), role)

    if body.user_ids is not None:
        count = len(set(body.user_ids))
    else:
        source = next((r for r in roles if r["id"] == body.from_role_id), None)
        if source is None:
            raise HTTPException(status_code=404, detail="Rôle source introuvable")
        count = source["members"]
    if body.confirm_count != count:
        raise HTTPException(
            status_code=409,
            detail=f"Le nombre a changé : {count} membre(s) concerné(s). Vérifiez puis confirmez à nouveau.",
        )

    actor_id = int(user["sub"])
    details = {"role_id": str(role_id), "role": role["name"], "action": body.action, "count": count,
               "from_role_id": body.from_role_id}
    payload = {"action": body.action, "user_ids": body.user_ids, "from_role_id": body.from_role_id,
               "actor_name": await _actor_name(user)}
    # Le bot refuse (422) plus de 500 membres, y compris via le rôle source (Ruling R9) : relayé tel quel.
    job = await _bot_write("member_role_bulk", actor_id, "post", f"/discord/roles/{role_id}/bulk", payload,
                           details=details, target_id=role_id, target_name=role["name"])
    await admin._log("member_role_bulk", actor_id, role_id, {**details, "job_id": job["job_id"]},
                     target_name=role["name"])
    return {"job_id": job["job_id"]}


@router.get("/jobs/{job_id}")
async def job_status(job_id: str, user: dict = Depends(get_current_user)):
    """État d'un travail du bot ; 404 = bot redémarré ou travail expiré (le site affiche « interrompu »)."""
    require_any_permission(user, "members.roles", "roles.manage")
    return await admin._bot("get", f"/discord/jobs/{job_id}")


# ── Règles automatiques ─────────────────────────────────────────────────────

def find_conflicts(rules: list[dict], role_names: dict[str, str] | None = None) -> list[str]:
    """Deux règles actives sur le même rôle dont l'une a « retirer si perdu ».

    Portage de ``bot/utils/role_rules.find_conflicts`` (Ruling R1) : même règle, mêmes cas de test.
    """
    role_names = role_names or {}
    by_role: dict[int, list[dict]] = {}
    for r in rules:
        if r["active"] and r["role_id"] is not None:
            by_role.setdefault(int(r["role_id"]), []).append(r)
    return [
        f"Le rôle « {role_names.get(str(role_id), role_id)} » est visé par {len(group)} règles actives "
        "dont l'une le retire à la perte de la condition : elles se contrediraient."
        for role_id, group in by_role.items()
        if len(group) > 1 and any(r["remove_when_lost"] for r in group)
    ]


def _rule_out(row: dict, roles_by_id: dict[str, dict]) -> dict:
    role_id = None if row["role_id"] is None else str(row["role_id"])
    role = roles_by_id.get(role_id) if role_id else None
    previous_role_id = row.get("previous_role_id")
    out = {
        "id": row["id"],
        **{k: row[k] for k in RULE_FIELDS},
        "role_id": role_id,
        "previous_role_id": None if previous_role_id is None else str(previous_role_id),
        "role_name": role["name"] if role else None,
        "missing_role": role_id is not None and role is None,
    }
    if "achievement_name" in row:
        out["achievement_name"] = row["achievement_name"]
    return out


async def _validate_condition(ctype: str, value: str) -> None:
    def refuse(detail: str):
        raise HTTPException(status_code=422, detail=detail)

    if ctype not in CONDITIONS:
        refuse(f"Condition inconnue : {ctype}")
    if ctype == "grade":
        if not await db.fetchval("SELECT 1 FROM grades WHERE slug = $1", value):
            refuse(f"Grade inconnu : {value}")
        return
    if ctype == "achievement":
        if not value.isdigit() or not await db.fetchval("SELECT 1 FROM achievements WHERE id = $1", int(value)):
            refuse("Ce succès n'existe pas")
        return
    try:
        number = float(value)
    except ValueError:
        number = -1.0
    if not number >= 0 or number == float("inf"):
        refuse("La valeur doit être un nombre positif ou nul")
    if ctype != "voice_hours" and not number.is_integer():
        refuse("La valeur doit être un nombre entier pour cette condition")


def _validate_target(rule: dict) -> None:
    if rule["role_id"] is not None and rule["create_role_name"] is not None:
        raise HTTPException(status_code=422,
                            detail="Choisissez l'un ou l'autre : un rôle existant ou un rôle créé au premier déblocage")
    if rule["role_id"] is None:
        if rule["create_role_name"] is None:
            raise HTTPException(status_code=422, detail="Choisissez un rôle cible")
        if rule["condition_type"] != "achievement":
            raise HTTPException(status_code=422,
                                detail="« Créer au premier déblocage » est réservé aux règles de succès")


def _bot_can_give(role: dict | None) -> None:
    """422 si le bot ne peut pas gérer le rôle cible (conflit refusé à l'enregistrement)."""
    if role is None:
        raise HTTPException(status_code=422, detail="Rôle cible introuvable sur le serveur")
    if role["managed"]:
        raise HTTPException(status_code=422,
                            detail="Ce rôle est géré par une intégration : le bot ne peut pas le donner")
    if not role["below_bot"]:
        raise HTTPException(status_code=422,
                            detail="Ce rôle n'est pas sous le rôle le plus haut du bot : il ne pourrait pas le donner")


def _check_created_role(rule: dict, roles: list[dict], actor: dict, *, target_changed: bool) -> None:
    """« Créer au premier déblocage » : le bot réutilisera un rôle de même nom s'il existe.

    Ce rôle homonyme est donc la vraie cible : même contrôle qu'un ``role_id`` (C1). Sans
    homonyme, le rôle sera créé tout en bas (position 1).
    """
    homonym = next((r for r in roles if r["name"] == rule["create_role_name"]), None)
    if homonym is None:
        _require_outranks(actor, 1)
        return
    if target_changed:
        _bot_can_give(homonym)
    _require_outranks(actor, homonym["position"])


def _check_group(rule: dict, group: list[dict], roles: list[dict], actor: dict) -> None:
    """Groupe exclusif (I2) : le bot retire aux membres les rôles des règles perdantes du groupe.

    Une règle du groupe peut donc faire retirer le rôle de chacune des autres : l'acteur doit
    les surclasser toutes. Les seuils ne se comparent qu'entre conditions de même type.
    """
    if any(r["condition_type"] != rule["condition_type"] for r in group):
        raise HTTPException(
            status_code=422,
            detail=f"Le groupe « {rule['exclusive_group']} » réunit déjà des règles d'un autre type de "
                   "condition : un groupe ne compare que des seuils de même type.",
        )
    roles_by_id = {r["id"]: r for r in roles}
    for other in group:
        if other["role_id"] is not None:
            role = roles_by_id.get(str(other["role_id"]))
        else:
            role = next((r for r in roles if r["name"] == other["create_role_name"]), None)
        if role is not None and not outranks(actor, role["position"]):
            raise HTTPException(
                status_code=403,
                detail=f"Le groupe « {rule['exclusive_group']} » contient le rôle « {role['name']} », au niveau "
                       "du vôtre ou au-dessus : une règle de ce groupe pourrait le retirer.",
            )


async def _check_rule(rule: dict, *, rule_id: int | None, role_changed: bool, roles: list[dict],
                      actor: dict, previous_role_id: int | None = None,
                      name_changed: bool = True) -> None:
    """Valide une règle complète (création ou résultat d'un PATCH) ; lève 422/403."""
    await _validate_condition(rule["condition_type"], rule["condition_value"])
    _validate_target(rule)
    roles_by_id = {r["id"]: r for r in roles}
    if rule["role_id"] is not None:
        role = roles_by_id.get(str(rule["role_id"]))
        if role_changed:
            _bot_can_give(role)
        if role is not None:
            _require_outranks(actor, role["position"])
    elif rule["create_role_name"] is not None:
        _check_created_role(rule, roles, actor, target_changed=role_changed or name_changed)
    if previous_role_id is not None and previous_role_id != rule["role_id"]:
        previous = roles_by_id.get(str(previous_role_id))
        if previous is not None:
            _require_outranks(actor, previous["position"])

    others = [dict(r) for r in await db.fetch("SELECT * FROM role_rules ORDER BY id") if r["id"] != rule_id]
    if rule["exclusive_group"] is not None:
        _check_group(rule, [r for r in others if r["exclusive_group"] == rule["exclusive_group"]],
                     roles, actor)
    conflicts = find_conflicts(others + [rule], {r["id"]: r["name"] for r in roles})
    if conflicts:
        raise HTTPException(status_code=422, detail=" ".join(conflicts))


async def _rule(rule_id: int) -> dict:
    row = await db.fetchrow("SELECT * FROM role_rules WHERE id = $1", rule_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Règle introuvable")
    return dict(row)


async def _reload() -> bool:
    """Demande au bot de recharger ses règles ; un échec n'annule pas l'écriture déjà faite."""
    try:
        await admin._bot("post", "/role-rules/reload")
        return True
    except Exception as e:  # bot injoignable ou moteur absent : il relira au redémarrage
        logger.warning(f"rechargement des règles refusé par le bot : {e}")
        return False


def _rule_args(rule: dict) -> list:
    return [int(rule["role_id"]) if k == "role_id" and rule[k] is not None else rule[k] for k in RULE_FIELDS]


@router.get("/role-rules")
async def list_rules(user: dict = Depends(get_current_user)):
    require_permission(user, "roles.manage")
    roles_by_id = {r["id"]: r for r in await _roles()}
    rows = await db.fetch(
        """SELECT r.*, a.name AS achievement_name
           FROM role_rules r
           LEFT JOIN achievements a ON r.condition_type = 'achievement' AND a.id::text = r.condition_value
           ORDER BY r.id"""
    )
    return {"rules": [_rule_out(dict(row), roles_by_id) for row in rows]}


@router.post("/role-rules")
async def create_rule(body: RuleCreate, user: dict = Depends(get_current_user)):
    require_permission(user, "roles.manage")
    if body.reconcile:
        raise HTTPException(status_code=422,
                            detail="Une nouvelle règle démarre en mode aperçu : consultez l'aperçu avant de l'appliquer")
    rule = body.model_dump()
    rule["role_id"] = None if rule["role_id"] is None else int(rule["role_id"])
    roles = await _roles()
    await _check_rule(rule, rule_id=None, role_changed=True, roles=roles, actor=await actor_rank(user))

    actor_id = int(user["sub"])
    row = dict(await db.fetchrow(
        f"""INSERT INTO role_rules ({", ".join(RULE_FIELDS)}, created_by)
            VALUES ({", ".join(f"${i}" for i in range(1, len(RULE_FIELDS) + 2))})
            RETURNING *""",
        *_rule_args(rule), actor_id,
    ))
    out = _rule_out(row, {r["id"]: r for r in roles})
    await admin._log("role_rule_create", actor_id, details={"rule_id": row["id"], **{k: out[k] for k in RULE_FIELDS}})
    return {"rule": out, "reloaded": await _reload()}


@router.patch("/role-rules/{rule_id}")
async def update_rule(rule_id: int, body: RuleUpdate, user: dict = Depends(get_current_user)):
    require_permission(user, "roles.manage")
    changes = body.model_dump(exclude_unset=True, exclude={"preview_seen"})
    for field in ("condition_type", "condition_value", "remove_when_lost", "active", "reconcile"):
        if field in changes and changes[field] is None:
            raise HTTPException(status_code=422, detail=f"Valeur requise : {field}")
    existing = await _rule(rule_id)
    if changes.get("reconcile") and not existing["reconcile"] and not body.preview_seen:
        raise HTTPException(status_code=422,
                            detail="Consultez l'aperçu de la règle avant d'activer l'application automatique")

    rule = {**existing, **changes}
    if "role_id" in changes and changes["role_id"] is not None:
        rule["role_id"] = int(changes["role_id"])
    role_changed = rule["role_id"] != existing["role_id"]
    roles = await _roles()
    await _check_rule(rule, rule_id=rule_id, role_changed=role_changed, roles=roles,
                      actor=await actor_rank(user), previous_role_id=existing["role_id"],
                      name_changed=rule["create_role_name"] != existing["create_role_name"])

    # L'ancien rôle est mémorisé : apply n'acceptera de retirer que lui (remove_previous_role_id).
    previous_role_id = existing["role_id"] if role_changed else existing.get("previous_role_id")
    row = await db.fetchrow(
        f"""UPDATE role_rules SET {", ".join(f"{k} = ${i}" for i, k in enumerate(RULE_FIELDS, start=2))},
                                  previous_role_id = ${len(RULE_FIELDS) + 2}, updated_at = NOW()
            WHERE id = $1 RETURNING *""",
        rule_id, *_rule_args(rule), previous_role_id,
    )
    if row is None:  # supprimée entre la lecture et l'écriture
        raise HTTPException(status_code=404, detail="Règle introuvable")
    roles_by_id = {r["id"]: r for r in roles}
    previous_role = None
    if role_changed and existing["role_id"] is not None:
        old = roles_by_id.get(str(existing["role_id"]))
        if old is not None:
            previous_role = {"id": old["id"], "name": old["name"], "members": old["members"]}

    await admin._log("role_rule_update", int(user["sub"]), details={"rule_id": rule_id, "changes": changes})
    return {"rule": _rule_out(dict(row), roles_by_id), "previous_role": previous_role,
            "reloaded": await _reload()}


@router.delete("/role-rules/{rule_id}")
async def delete_rule(rule_id: int, user: dict = Depends(get_current_user)):
    require_permission(user, "roles.manage")
    existing = await _rule(rule_id)
    if existing["role_id"] is not None:
        role = next((r for r in await _roles() if r["id"] == str(existing["role_id"])), None)
        if role is not None:
            _require_outranks(await actor_rank(user), role["position"])
    if await db.fetchrow("DELETE FROM role_rules WHERE id = $1 RETURNING id", rule_id) is None:
        raise HTTPException(status_code=404, detail="Règle introuvable")
    await admin._log("role_rule_delete", int(user["sub"]), details={
        "rule_id": rule_id, "condition_type": existing["condition_type"],
        "condition_value": existing["condition_value"],
        "role_id": None if existing["role_id"] is None else str(existing["role_id"]),
    })
    return {"ok": True, "reloaded": await _reload()}


@router.get("/role-rules/{rule_id}/preview")
async def preview_rule(rule_id: int, user: dict = Depends(get_current_user)):
    require_permission(user, "roles.manage")
    return await admin._bot("get", f"/role-rules/{rule_id}/preview")


@router.post("/role-rules/{rule_id}/apply")
async def apply_rule(rule_id: int, body: RuleApply, user: dict = Depends(get_current_user)):
    """Réconcilie la règle sur tout le serveur (travail du bot, Ruling R8).

    ``remove_previous_role_id`` : après un changement de rôle, retire aussi l'ancien rôle à tous
    ceux qui le portent (lot ``from_role_id``, limité à 500 membres par le bot). C'est un retrait
    en lot : il exige ``members.roles``, ne vise que l'ancien rôle mémorisé par le dernier PATCH
    qui a changé le rôle de la règle, et ``confirm_previous_members`` doit égaler son nombre de
    membres actuel (sinon 409).
    """
    require_permission(user, "roles.manage")
    if not body.confirm:
        raise HTTPException(status_code=422, detail="Confirmation requise pour appliquer la règle")
    if body.remove_previous_role_id is not None:
        require_permission(user, "members.roles")
    rule = await _rule(rule_id)
    roles = await _roles()
    roles_by_id = {r["id"]: r for r in roles}
    actor = await actor_rank(user)
    target = roles_by_id.get(str(rule["role_id"])) if rule["role_id"] is not None else None
    if target is not None:
        _require_outranks(actor, target["position"])
    elif rule["role_id"] is None and rule["create_role_name"] is not None:
        _check_created_role(rule, roles, actor, target_changed=True)

    previous = None
    if body.remove_previous_role_id is not None:
        if rule["role_id"] is not None and body.remove_previous_role_id == str(rule["role_id"]):
            raise HTTPException(status_code=422, detail="L'ancien rôle est le rôle actuel de la règle")
        recorded = rule.get("previous_role_id")
        if recorded is None or body.remove_previous_role_id != str(recorded):
            raise HTTPException(status_code=422, detail="Ce rôle n'est pas l'ancien rôle de la règle")
        previous = roles_by_id.get(body.remove_previous_role_id)
        if previous is None:
            raise HTTPException(status_code=404, detail="Ancien rôle introuvable")
        _require_manageable(actor, previous)
        if body.confirm_previous_members != previous["members"]:
            raise HTTPException(
                status_code=409,
                detail=f"Le nombre a changé : l'ancien rôle compte maintenant {previous['members']} membre(s). "
                       "Vérifiez puis confirmez à nouveau.",
            )

    actor_id = int(user["sub"])
    details = {"rule_id": rule_id, "remove_previous_role_id": body.remove_previous_role_id}
    if previous is not None:
        details["previous_members"] = previous["members"]
    remove_job_id = None
    if previous is not None:  # d'abord : un refus (> 500 membres) n'aura rien lancé
        job = await _bot_write(
            "role_rule_apply", actor_id, "post", f"/discord/roles/{previous['id']}/bulk",
            {"action": "remove", "user_ids": None, "from_role_id": previous["id"],
             "actor_name": await _actor_name(user)},
            details=details,
        )
        remove_job_id = job["job_id"]
    job = await _bot_write("role_rule_apply", actor_id, "post", f"/role-rules/{rule_id}/apply", {},
                           details={**details, "remove_job_id": remove_job_id})
    await admin._log("role_rule_apply", actor_id, details={
        **details, "job_id": job["job_id"], "remove_job_id": remove_job_id,
    })
    return {"job_id": job["job_id"], "remove_job_id": remove_job_id}
