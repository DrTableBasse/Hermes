"""Gestion des droits par rôle et anti-escalade (étape 2, tâche 4)."""
import json

import pytest
from fastapi import HTTPException

from limiter import limiter
from permissions import PERMISSIONS
from routes import admin
from routes.access import check_escalation

# Rôles tels que renvoyés par le bot (/discord/roles), position décroissante.
ROLES = [
    {"id": "500", "name": "Chef", "color": 1, "position": 10, "managed": False},
    {"id": "400", "name": "Modo", "color": 2, "position": 5, "managed": False},
    {"id": "300", "name": "Hermes", "color": 0, "position": 4, "managed": True},
    {"id": "200", "name": "Membre", "color": 3, "position": 1, "managed": False},
]

SELECT_ALL = "SELECT discord_role_id, permission FROM site_permissions"
SELECT_ONE = "SELECT permission FROM site_permissions WHERE"


# ── check_escalation (fonction pure) ────────────────────────────────────────

def test_cannot_edit_role_at_or_above_own():
    actor = {"top_position": 10, "is_owner": False, "permissions": {"permissions.manage", "moderation.view"}}
    assert check_escalation(actor, 10, set(), {"moderation.view"}) is not None
    assert check_escalation(actor, 11, set(), {"moderation.view"}) is not None
    assert check_escalation(actor, 9, set(), {"moderation.view"}) is None


def test_cannot_grant_or_remove_what_actor_lacks():
    actor = {"top_position": 10, "is_owner": False, "permissions": {"permissions.manage"}}
    assert check_escalation(actor, 5, set(), {"settings.manage"}) is not None
    assert check_escalation(actor, 5, {"settings.manage"}, set()) is not None


def test_unchanged_rights_the_actor_lacks_do_not_block():
    actor = {"top_position": 10, "is_owner": False, "permissions": {"moderation.view"}}
    # settings.manage était déjà là et reste : seul moderation.view change.
    assert check_escalation(actor, 5, {"settings.manage"}, {"settings.manage", "moderation.view"}) is None


def test_owner_is_exempt():
    assert check_escalation({"top_position": 0, "is_owner": True, "permissions": set()}, 99, set(), {"settings.manage"}) is None


# ── Routes ──────────────────────────────────────────────────────────────────

@pytest.fixture
def bot(monkeypatch):
    """Bot factice : rôles du serveur et rang de chaque membre (``ranks[discord_id]``)."""
    state = {"roles": [dict(r) for r in ROLES], "ranks": {}, "calls": []}

    async def fake_bot(method, path, **kwargs):
        state["calls"].append((method, path))
        if path == "/discord/roles":
            return {"roles": state["roles"]}
        if path.startswith("/discord/members/") and path.endswith("/rank"):
            uid = path.split("/")[3]
            if uid not in state["ranks"]:
                raise HTTPException(status_code=404, detail="Member not found")
            return state["ranks"][uid]
        raise AssertionError(f"appel bot inattendu : {method} {path}")

    monkeypatch.setattr(admin, "_bot", fake_bot)
    monkeypatch.setattr(limiter, "enabled", False)
    return state


def _rank(top, *, owner=False):
    return {"top_position": top, "is_owner": owner, "role_ids": []}


def _grants(fake_db, rows):
    """``rows`` : {role_id: [droits]} pour la lecture globale et par rôle."""
    fake_db.on(SELECT_ALL, [
        {"discord_role_id": int(rid), "permission": p} for rid, perms in rows.items() for p in perms
    ])
    fake_db.on(SELECT_ONE, lambda sql, rid: [{"permission": p} for p in rows.get(str(rid), [])])


def _writes(fake_db):
    return [c for c in fake_db.calls if c[0] == "execute" and "insert into site_permissions" in c[1].lower()]


def _audit(fake_db):
    return [c for c in fake_db.calls if c[0] == "execute" and "insert into audit_events" in c[1].lower()]


def test_get_requires_permissions_manage(client, fake_db, bot, session_with):
    session_with(set(PERMISSIONS) - {"permissions.manage"})
    r = client.get("/admin/access")
    assert r.status_code == 403
    assert r.json()["detail"] == f"Droit requis : {PERMISSIONS['permissions.manage']}"


def test_get_lists_catalog_roles_and_actor(client, fake_db, bot, session_with):
    bot["ranks"]["1"] = _rank(5)
    _grants(fake_db, {"200": ["moderation.view"], "400": ["tickets.manage", "admin.view"]})
    session_with({"permissions.manage", "moderation.view"})

    r = client.get("/admin/access")
    assert r.status_code == 200
    body = r.json()
    assert body["catalog"] == [{"key": k, "label": v} for k, v in PERMISSIONS.items()]
    assert body["actor"] == {"top_position": 5, "is_owner": False,
                             "permissions": ["moderation.view", "permissions.manage"]}
    by_id = {role["id"]: role for role in body["roles"]}
    assert [role["id"] for role in body["roles"]] == ["500", "400", "300", "200"]
    assert by_id["400"] == {"id": "400", "name": "Modo", "color": 2, "position": 5, "managed": False,
                            "permissions": ["admin.view", "tickets.manage"], "editable": False}
    assert by_id["500"]["editable"] is False
    assert by_id["300"]["editable"] is True and by_id["300"]["managed"] is True
    assert by_id["200"]["permissions"] == ["moderation.view"] and by_id["200"]["editable"] is True


def test_get_owner_can_edit_every_role(client, fake_db, bot, session_with):
    bot["ranks"]["1"] = _rank(0, owner=True)
    session_with((), is_admin=True)
    body = client.get("/admin/access").json()
    assert all(role["editable"] for role in body["roles"])
    assert body["actor"]["is_owner"] is True
    assert body["actor"]["permissions"] == sorted(PERMISSIONS)


def test_get_actor_absent_from_guild_edits_nothing(client, fake_db, bot, session_with):
    session_with({"permissions.manage"})
    body = client.get("/admin/access").json()
    assert body["actor"]["top_position"] == 0 and body["actor"]["is_owner"] is False
    assert not any(role["editable"] for role in body["roles"])


def test_put_requires_permissions_manage(client, fake_db, bot, session_with):
    session_with(set(PERMISSIONS) - {"permissions.manage"})
    assert client.put("/admin/access/200", json={"permissions": []}).status_code == 403
    assert _writes(fake_db) == []


def test_put_unknown_permission_is_422(client, fake_db, bot, session_with):
    bot["ranks"]["1"] = _rank(0, owner=True)
    session_with((), is_admin=True)
    r = client.put("/admin/access/200", json={"permissions": ["admin.view", "pirate.all"]})
    assert r.status_code == 422
    assert "pirate.all" in r.json()["detail"]
    assert _writes(fake_db) == [] and _audit(fake_db) == []


def test_put_unknown_role_is_404(client, fake_db, bot, session_with):
    bot["ranks"]["1"] = _rank(0, owner=True)
    session_with((), is_admin=True)
    r = client.put("/admin/access/999", json={"permissions": ["admin.view"]})
    assert r.status_code == 404
    assert _writes(fake_db) == []


def test_put_role_at_own_position_is_403(client, fake_db, bot, session_with):
    bot["ranks"]["1"] = _rank(5)
    session_with({"permissions.manage", "moderation.view"})
    r = client.put("/admin/access/400", json={"permissions": ["moderation.view"]})
    assert r.status_code == 403
    assert _writes(fake_db) == [] and _audit(fake_db) == []


def test_put_granting_a_right_actor_lacks_is_403(client, fake_db, bot, session_with):
    bot["ranks"]["1"] = _rank(5)
    _grants(fake_db, {})
    session_with({"permissions.manage"})
    r = client.put("/admin/access/200", json={"permissions": ["settings.manage"]})
    assert r.status_code == 403
    assert "settings.manage" in r.json()["detail"]
    assert _writes(fake_db) == []


def test_put_removing_a_right_actor_lacks_is_403(client, fake_db, bot, session_with):
    bot["ranks"]["1"] = _rank(5)
    _grants(fake_db, {"200": ["settings.manage"]})
    session_with({"permissions.manage"})
    r = client.put("/admin/access/200", json={"permissions": []})
    assert r.status_code == 403
    assert _writes(fake_db) == []


def test_admin_role_holder_is_not_exempt_from_position(client, fake_db, bot, session_with):
    # is_admin sans être propriétaire : tous les droits, mais pas au-dessus de son rang.
    bot["ranks"]["1"] = _rank(5)
    _grants(fake_db, {})
    session_with((), is_admin=True)
    assert client.put("/admin/access/500", json={"permissions": ["admin.view"]}).status_code == 403
    assert client.put("/admin/access/400", json={"permissions": ["admin.view"]}).status_code == 403
    r = client.put("/admin/access/200", json={"permissions": ["settings.manage"]})
    assert r.status_code == 200


def test_put_replaces_rights_and_journals(client, fake_db, bot, session_with):
    bot["ranks"]["1"] = _rank(5)
    _grants(fake_db, {"200": ["moderation.view", "tickets.manage"]})
    session_with({"permissions.manage", "moderation.view", "tickets.manage", "admin.view"})

    r = client.put("/admin/access/200",
                   json={"permissions": ["admin.view", "tickets.manage", "admin.view"]})
    assert r.status_code == 200, r.text
    assert r.json() == {"id": "200", "permissions": ["admin.view", "tickets.manage"]}

    writes = _writes(fake_db)
    assert len(writes) == 1
    _, sql, args = writes[0]
    assert "delete from site_permissions" in sql.lower()  # remplacement : les absents sont retirés
    assert args == (200, ["admin.view", "tickets.manage"], 1)

    audits = _audit(fake_db)
    assert len(audits) == 1
    _, _, (kind, action, source, actor_id, _actor_name, target_id, target_name, details, success) = audits[0]
    assert (kind, action, source, actor_id, target_id, success) == ("site_access", "update", "site", 1, 200, True)
    assert target_name == "Membre"
    assert json.loads(details) == {"role": "Membre",
                                   "before": ["moderation.view", "tickets.manage"],
                                   "after": ["admin.view", "tickets.manage"]}


def test_owner_can_edit_any_role_with_any_right(client, fake_db, bot, session_with):
    bot["ranks"]["1"] = _rank(0, owner=True)
    _grants(fake_db, {"500": ["analytics.view"]})
    session_with((), is_admin=True)
    r = client.put("/admin/access/500", json={"permissions": ["settings.manage"]})
    assert r.status_code == 200
    assert _writes(fake_db)[0][2] == (500, ["settings.manage"], 1)
