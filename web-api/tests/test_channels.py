"""Salons et modèles d'accès (étape 5, tâche 3) : droits, anti-escalade, relais du bot, journal."""
import json
import sys

import httpx
import pytest
from fastapi import HTTPException

from limiter import limiter
from permissions import PERMISSIONS
from routes import admin

STALE = "L'aperçu n'est plus à jour : relancez l'aperçu avant d'appliquer"

ROLES = [
    {"id": "800", "name": "Fondateur", "color": 1, "position": 15, "managed": False, "members": 1, "below_bot": False},
    {"id": "500", "name": "Chef", "color": 1, "position": 10, "managed": False, "members": 2, "below_bot": True},
    {"id": "400", "name": "Modo", "color": 2, "position": 5, "managed": False, "members": 3, "below_bot": True},
    {"id": "200", "name": "Membre", "color": 3, "position": 1, "managed": False, "members": 37, "below_bot": True},
]


def _ch(cid, name, type_="text", parent=None, template=None, visible=True):
    return {"id": cid, "name": name, "type": type_, "position": 0, "parent_id": parent, "overwrites": 0,
            "template": template, "visible_to_actor": visible}


TREE = [
    _ch("10", "general"),
    _ch("20", "Jeux", "category"),
    _ch("21", "fortnite", parent="20"),
    _ch("30", "staff-only", template={"template": "staff", "roles": ["400"], "applied_by": "1",
                                       "applied_at": "2026-11-24T10:00:00+00:00"}, visible=False),
]

CHANGES = [{"target_id": "100", "target_type": "role", "target_name": "@everyone", "action": "add",
            "before": None, "after": {"allow": [], "deny": ["view_channel"]}}]


@pytest.fixture
def bot(monkeypatch):
    """Bot factice : arbre, rôles, rangs, aperçus (jeton ``tok-1``) et erreurs programmables."""
    state = {
        "ranks": {"1": {"top_position": 5, "is_owner": False}},
        "calls": [],
        "errors": {},  # (méthode, chemin) → exception levée
        "token": "tok-1",
        "apply": {"applied": 1, "failed": [], "memo_failed": []},
    }

    async def fake_bot(method, path, **kwargs):
        state["calls"].append((method, path, kwargs.get("json"), kwargs.get("params"), kwargs.get("timeout")))
        if (method, path) in state["errors"]:
            raise state["errors"][(method, path)]
        if path == "/discord/channels/tree":
            return {"channels": [dict(c) for c in TREE],
                    "templates": ["public", "role_required", "announcements", "staff"]}
        if path == "/discord/roles":
            return {"roles": ROLES}
        if path.startswith("/discord/members/") and path.endswith("/rank"):
            uid = path.split("/")[3]
            if uid not in state["ranks"]:
                raise HTTPException(404, "Member not found")
            return state["ranks"][uid]
        if path == "/discord/channels" and method == "post":
            body = kwargs["json"]
            return {"id": "99", "name": body["name"], "type": body["type"], "parent_id": body["parent_id"]}
        if path.startswith("/discord/channels/") and method == "patch":
            return {"id": path.split("/")[3], "name": kwargs["json"].get("name", "general"),
                    "position": 0, "parent_id": None}
        if path.startswith("/discord/channels/") and method == "delete":
            return {"ok": True}
        if path.endswith("/preview"):
            cid = "30" if "staff-resync" in path else path.split("/")[3]
            name = next(c["name"] for c in TREE if c["id"] == cid)
            return {"channels": [{"id": cid, "name": name, "type": "text", "changes": CHANGES}],
                    "count": 1, "token": state["token"]}
        if path.endswith("/apply"):
            return state["apply"]
        raise AssertionError(f"appel bot inattendu : {method} {path}")

    monkeypatch.setattr(admin, "_bot", fake_bot)
    monkeypatch.setattr(limiter, "enabled", False)
    return state


def _audit(fake_db):
    rows = []
    for method, sql, args in fake_db.calls:
        if method == "execute" and "insert into audit_events" in sql.lower():
            kind, action, source, actor_id, _name, target_id, target_name, details, success = args
            assert source == "site"
            rows.append({"kind": kind, "action": action, "actor_id": actor_id, "target_id": target_id,
                         "target_name": target_name, "details": json.loads(details), "success": success})
    return rows


def _paths(bot, method=None):
    return [c[1] for c in bot["calls"] if method is None or c[0] == method]


def _writes(bot):
    """Appels qui modifient Discord (hors lectures et aperçus)."""
    return [c for c in bot["calls"] if c[0] != "get" and not c[1].endswith("/preview")]


@pytest.fixture
def mod(session_with, fake_db, bot):
    """Membre non admin, rang 5, avec ``channels.manage``."""
    fake_db.on("from user_voice_data", {"name": "Bob"})
    return session_with({"channels.manage"})


# ── Droits ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("method,path,body", [
    ("get", "/admin/channels", None),
    ("post", "/admin/channels", {"name": "x", "type": "text"}),
    ("patch", "/admin/channels/10", {"name": "y"}),
    ("delete", "/admin/channels/10", {"confirm_name": "general"}),
    ("post", "/admin/channels/10/template/preview", {"template": "public"}),
    ("post", "/admin/channels/10/template/apply", {"template": "public", "token": "tok-1"}),
    ("post", "/admin/channels/staff-resync/preview", None),
    ("post", "/admin/channels/staff-resync/apply", {"token": "tok-1"}),
])
def test_every_route_requires_channels_manage(client, fake_db, bot, session_with, method, path, body):
    session_with(set(PERMISSIONS) - {"channels.manage"})
    r = client.request(method.upper(), path, json=body)
    assert r.status_code == 403
    assert r.json()["detail"] == "Droit requis : Gérer les salons"
    assert bot["calls"] == []


def test_unauthenticated_is_401(client, fake_db, bot):
    assert client.get("/admin/channels").status_code == 401


# ── GET /admin/channels ─────────────────────────────────────────────────────

def test_list_channels_passes_actor_and_marks_assignable_roles(client, mod, bot):
    r = client.get("/admin/channels")
    assert r.status_code == 200
    data = r.json()
    assert bot["calls"][0][3] == {"actor_id": "1"}
    assert [c["id"] for c in data["channels"]] == ["10", "20", "21"]  # « staff-only » invisible : masqué
    assert {r["id"]: r["assignable"] for r in data["roles"]} == {"800": False, "500": False,
                                                                  "400": False, "200": True}
    assert data["templates"] == ["public", "role_required", "announcements"]  # « staff » : admins
    assert data["actor"]["is_admin"] is False and data["actor"]["top_position"] == 5
    assert data["staff_resync"] is None


def test_list_channels_hides_every_channel_invisible_to_actor(client, mod, bot, monkeypatch):
    # Catégorie invisible, salon visible dedans : la catégorie disparaît (nom compris), le salon reste.
    monkeypatch.setattr(sys.modules[__name__], "TREE",
                        [TREE[0], _ch("20", "Jeux-secrets", "category", visible=False), *TREE[2:]])
    r = client.get("/admin/channels")
    assert [c["id"] for c in r.json()["channels"]] == ["10", "21"]
    assert "staff-only" not in r.text and "Jeux-secrets" not in r.text


def test_list_channels_owner_sees_everything(client, mod, bot):
    bot["ranks"]["1"] = {"top_position": 0, "is_owner": True}
    data = client.get("/admin/channels").json()
    assert [c["id"] for c in data["channels"]] == ["10", "20", "21", "30"]


def test_list_channels_admin_sees_staff_template_and_pending_resync(client, fake_db, bot, session_with):
    # staff_roles passé de Modo (400) à Chef + Modo : le salon « staff » mémorisé est à resynchroniser.
    fake_db.on("from bot_settings", [{"key": "staff_roles", "value": "500, 400, 12345"}])
    session_with(is_admin=True)
    data = client.get("/admin/channels").json()
    assert "staff" in data["templates"]
    assert data["staff_resync"] == {"pending": 1, "channel_ids": ["30"], "staff_roles_set": True}


def test_list_channels_admin_nothing_pending_when_staff_roles_unchanged(client, fake_db, bot, session_with):
    fake_db.on("from bot_settings", [{"key": "staff_roles", "value": "400,999"}])  # 999 : rôle supprimé
    session_with(is_admin=True)
    assert client.get("/admin/channels").json()["staff_resync"] == {
        "pending": 0, "channel_ids": [], "staff_roles_set": True}


# ── POST / PATCH / DELETE ───────────────────────────────────────────────────

def test_create_channel_calls_bot_and_logs(client, mod, bot, fake_db):
    r = client.post("/admin/channels", json={"name": "  annonces ", "type": "announcement", "parent_id": "20"})
    assert r.status_code == 200
    assert _writes(bot)[0][:3] == ("post", "/discord/channels", {
        "name": "annonces", "type": "announcement", "parent_id": "20", "actor_id": "1", "actor_name": "Bob"})
    [row] = _audit(fake_db)
    assert (row["kind"], row["action"], row["target_id"], row["target_name"], row["success"]) == \
        ("channel", "channel_create", 99, "annonces", True)


@pytest.mark.parametrize("body", [
    {"name": "", "type": "text"}, {"name": "x" * 101, "type": "text"},
    {"name": "ok", "type": "media"}, {"name": "ok", "type": "text", "parent_id": "abc"},
])
def test_create_channel_validation_is_422(client, mod, bot, body):
    assert client.post("/admin/channels", json=body).status_code == 422
    assert bot["calls"] == []


def test_create_channel_bot_error_relayed_and_logged(client, mod, bot, fake_db):
    bot["errors"][("post", "/discord/channels")] = HTTPException(422, "Refusé par Discord : nom invalide")
    r = client.post("/admin/channels", json={"name": "x", "type": "text"})
    assert r.status_code == 422 and r.json()["detail"] == "Refusé par Discord : nom invalide"
    [row] = _audit(fake_db)
    assert row["success"] is False and row["details"]["error"] == "Refusé par Discord : nom invalide"


def test_update_channel_always_sends_actor_id_and_keeps_explicit_null_parent(client, mod, bot, fake_db):
    r = client.patch("/admin/channels/21", json={"parent_id": None})
    assert r.status_code == 200
    assert _writes(bot)[0][:3] == ("patch", "/discord/channels/21",
                                   {"parent_id": None, "actor_id": "1", "actor_name": "Bob"})
    [row] = _audit(fake_db)
    assert (row["kind"], row["action"], row["details"]) == ("channel", "channel_update",
                                                            {"changes": {"parent_id": None}})


def test_update_channel_absent_parent_is_not_sent(client, mod, bot):
    client.patch("/admin/channels/10", json={"name": "discussion"})
    assert _writes(bot)[0][2] == {"name": "discussion", "actor_id": "1", "actor_name": "Bob"}


@pytest.mark.parametrize("body", [{}, {"name": None}, {"position": -1}, {"position": None}])
def test_update_channel_invalid_is_422(client, mod, bot, body):
    assert client.patch("/admin/channels/10", json=body).status_code == 422
    assert bot["calls"] == []


def test_update_channel_not_visible_403_relayed(client, mod, bot, fake_db):
    bot["errors"][("patch", "/discord/channels/10")] = HTTPException(403, "Vous ne voyez pas ce salon")
    r = client.patch("/admin/channels/10", json={"name": "x"})
    assert r.status_code == 403 and r.json()["detail"] == "Vous ne voyez pas ce salon"
    assert _audit(fake_db)[0]["success"] is False


def test_delete_requires_exact_name(client, mod, bot, fake_db):
    r = client.request("DELETE", "/admin/channels/10", json={"confirm_name": "General"})
    assert r.status_code == 422
    assert "« general »" in r.json()["detail"]
    assert _writes(bot) == [] and _audit(fake_db) == []


def test_delete_missing_confirm_name_is_422(client, mod, bot):
    assert client.request("DELETE", "/admin/channels/10", json={}).status_code == 422
    assert _writes(bot) == []


def test_delete_unknown_channel_is_404(client, mod, bot):
    r = client.request("DELETE", "/admin/channels/77", json={"confirm_name": "x"})
    assert r.status_code == 404
    assert _writes(bot) == []


def test_delete_with_name_calls_bot_with_actor_and_logs(client, mod, bot, fake_db):
    r = client.request("DELETE", "/admin/channels/10", json={"confirm_name": " general "})
    assert r.status_code == 200
    assert ("delete", "/discord/channels/10", {"actor_id": "1", "actor_name": "Bob"}) in \
        [c[:3] for c in bot["calls"]]
    [row] = _audit(fake_db)
    assert (row["kind"], row["action"], row["target_id"], row["target_name"]) == \
        ("channel", "channel_delete", 10, "general")


def test_delete_non_empty_category_409_relayed(client, mod, bot, fake_db):
    bot["errors"][("delete", "/discord/channels/20")] = HTTPException(
        409, "Videz d'abord la catégorie : elle contient 1 salon(s)")
    r = client.request("DELETE", "/admin/channels/20", json={"confirm_name": "Jeux"})
    assert r.status_code == 409
    assert r.json()["detail"] == "Videz d'abord la catégorie : elle contient 1 salon(s)"
    [row] = _audit(fake_db)
    assert row["success"] is False and row["action"] == "channel_delete"


# ── Modèles : anti-escalade ─────────────────────────────────────────────────

@pytest.mark.parametrize("template", ["role_required", "announcements"])
@pytest.mark.parametrize("role_id", ["500", "400"])  # au-dessus de l'acteur (5), puis au même niveau
@pytest.mark.parametrize("step", ["preview", "apply"])
def test_role_at_or_above_actor_is_403(client, mod, bot, fake_db, template, role_id, step):
    r = client.post(f"/admin/channels/10/template/{step}",
                    json={"template": template, "roles": ["200", role_id], "token": "tok-1"})
    assert r.status_code == 403
    assert "au niveau du vôtre ou au-dessus" in r.json()["detail"]
    assert not [p for p in _paths(bot) if "/template/" in p]
    assert _audit(fake_db) == []


def test_owner_is_exempt_from_role_rank(client, mod, bot, fake_db):
    bot["ranks"]["1"] = {"top_position": 0, "is_owner": True}
    r = client.post("/admin/channels/10/template/apply",
                    json={"template": "role_required", "roles": ["800"], "token": "tok-1"})
    assert r.status_code == 200
    assert "/discord/channels/10/template/apply" in _paths(bot)


def test_actor_absent_from_server_cannot_cite_any_role(client, mod, bot):
    del bot["ranks"]["1"]
    r = client.post("/admin/channels/10/template/preview", json={"template": "role_required", "roles": ["200"]})
    assert r.status_code == 403


def test_unknown_role_is_404(client, mod, bot):
    r = client.post("/admin/channels/10/template/preview", json={"template": "role_required", "roles": ["1234"]})
    assert r.status_code == 404
    assert not [p for p in _paths(bot) if "/template/" in p]


def test_too_many_roles_is_422(client, mod, bot):
    r = client.post("/admin/channels/10/template/preview",
                    json={"template": "role_required", "roles": ["200"] * 26})
    assert r.status_code == 422


@pytest.mark.parametrize("step", ["preview", "apply"])
def test_staff_template_reserved_to_admins(client, mod, bot, fake_db, step):
    r = client.post(f"/admin/channels/10/template/{step}", json={"template": "staff", "token": "tok-1"})
    assert r.status_code == 403
    assert r.json()["detail"] == "Le modèle « Staff » et sa resynchronisation sont réservés aux administrateurs"
    assert bot["calls"] == []


def test_staff_template_allowed_for_admin(client, fake_db, bot, session_with):
    session_with(is_admin=True)
    bot["ranks"]["1"] = {"top_position": 0, "is_owner": True}  # salon 30 invisible : propriétaire exempté
    r = client.post("/admin/channels/30/template/preview", json={"template": "staff"})
    assert r.status_code == 200
    assert bot["calls"][-1][2] == {"template": "staff", "roles": [], "sync_children": False, "actor_id": "1"}


def test_public_on_hidden_staff_channel_by_member_who_cannot_see_it_is_403(client, mod, bot, fake_db):
    """Review Focus 1 : le bot calcule la visibilité ; son 403 est relayé, rien n'est appliqué."""
    hidden = HTTPException(403, "Vous ne voyez pas ce salon dans Discord")
    bot["errors"][("post", "/discord/channels/10/template/preview")] = hidden
    r = client.post("/admin/channels/10/template/preview", json={"template": "public"})
    assert r.status_code == 403 and r.json()["detail"] == "Vous ne voyez pas ce salon dans Discord"
    r = client.post("/admin/channels/10/template/apply", json={"template": "public", "token": "tok-1"})
    assert r.status_code == 403
    assert "/discord/channels/10/template/apply" not in _paths(bot)
    [row] = _audit(fake_db)
    assert (row["kind"], row["action"], row["success"]) == ("permission", "channel_template_apply", False)


# ── Modèles : aperçu et application ─────────────────────────────────────────

def test_preview_forwards_actor_and_returns_bot_payload(client, mod, bot):
    r = client.post("/admin/channels/20/template/preview",
                    json={"template": "role_required", "roles": ["200"], "sync_children": True})
    assert r.status_code == 200
    assert r.json()["token"] == "tok-1" and r.json()["count"] == 1
    method, path, body, _, timeout = bot["calls"][-1]
    assert (method, path) == ("post", "/discord/channels/20/template/preview")
    assert body == {"template": "role_required", "roles": ["200"], "sync_children": True, "actor_id": "1"}
    assert timeout == 5.0


def test_apply_sends_token_actor_and_logs_applied_changes(client, mod, bot, fake_db):
    r = client.post("/admin/channels/10/template/apply",
                    json={"template": "role_required", "roles": ["200"], "token": "tok-1"})
    assert r.status_code == 200
    assert r.json() == {"applied": 1, "failed": [], "memo_failed": []}
    method, path, body, _, timeout = bot["calls"][-1]
    assert (method, path, timeout) == ("post", "/discord/channels/10/template/apply", 40.0)
    assert body == {"template": "role_required", "roles": ["200"], "sync_children": False,
                    "actor_id": "1", "token": "tok-1", "actor_name": "Bob"}
    [row] = _audit(fake_db)
    assert (row["kind"], row["action"], row["target_id"], row["target_name"], row["success"]) == \
        ("permission", "channel_template_apply", 10, "general", True)
    assert row["details"] == {"template": "role_required", "roles": ["200"], "sync_children": False,
                              "count": 1, "applied": 1,
                              "changes": [{"id": "10", "name": "general", "changes": CHANGES}]}


def test_apply_stale_preview_is_409_without_writing(client, mod, bot, fake_db):
    """Review Focus 3 : l'état a changé depuis l'aperçu (jeton recalculé différent) → 409."""
    bot["token"] = "tok-2"
    r = client.post("/admin/channels/10/template/apply", json={"template": "public", "token": "tok-1"})
    assert r.status_code == 409 and r.json()["detail"] == STALE
    assert "/discord/channels/10/template/apply" not in _paths(bot)
    [row] = _audit(fake_db)
    assert row["success"] is False and row["details"]["error"] == STALE


def test_apply_bot_409_relayed(client, mod, bot, fake_db):
    """Changement entre l'aperçu de contrôle et l'application : le 409 du bot est relayé."""
    bot["errors"][("post", "/discord/channels/10/template/apply")] = HTTPException(409, STALE)
    r = client.post("/admin/channels/10/template/apply", json={"template": "public", "token": "tok-1"})
    assert r.status_code == 409 and r.json()["detail"] == STALE
    assert _audit(fake_db)[0]["success"] is False


def test_apply_bot_403_on_role_above_relayed(client, mod, bot, fake_db):
    bot["errors"][("post", "/discord/channels/10/template/apply")] = HTTPException(
        403, "Impossible de modifier la surcharge du rôle « Chef »")
    r = client.post("/admin/channels/10/template/apply", json={"template": "public", "token": "tok-1"})
    assert r.status_code == 403 and "Chef" in r.json()["detail"]


def test_apply_partial_failure_and_memo_failed_are_logged(client, mod, bot, fake_db):
    bot["apply"] = {"applied": 0, "failed": [{"id": "10", "name": "general", "error": "Forbidden"}],
                    "memo_failed": ["11"]}
    r = client.post("/admin/channels/10/template/apply", json={"template": "public", "token": "tok-1"})
    assert r.status_code == 200
    assert r.json()["memo_failed"] == ["11"]
    [row] = _audit(fake_db)
    assert row["success"] is False
    assert row["details"]["changes"] == []  # le salon en échec n'a rien reçu
    assert row["details"]["failed"] == [{"id": "10", "name": "general", "error": "Forbidden"}]
    assert row["details"]["memo_failed"] == ["11"]


def test_apply_memo_failed_alone_keeps_success(client, mod, bot, fake_db):
    bot["apply"] = {"applied": 1, "failed": [], "memo_failed": ["10"]}
    client.post("/admin/channels/10/template/apply", json={"template": "public", "token": "tok-1"})
    [row] = _audit(fake_db)
    assert row["success"] is True and row["details"]["memo_failed"] == ["10"]


def test_apply_timeout_is_504_and_logged(client, mod, bot, fake_db):
    bot["errors"][("post", "/discord/channels/10/template/apply")] = httpx.ReadTimeout("lent")
    r = client.post("/admin/channels/10/template/apply", json={"template": "public", "token": "tok-1"})
    assert r.status_code == 504
    assert _audit(fake_db)[0]["success"] is False


def test_bot_unreachable_is_503(client, mod, bot):
    bot["errors"][("get", "/discord/channels/tree")] = httpx.ConnectError("down")
    assert client.get("/admin/channels").status_code == 503


# ── Resynchronisation « staff » ─────────────────────────────────────────────

@pytest.mark.parametrize("path,body", [
    ("/admin/channels/staff-resync/preview", None),
    ("/admin/channels/staff-resync/apply", {"token": "tok-1"}),
])
def test_staff_resync_reserved_to_admins(client, mod, bot, path, body):
    r = client.post(path, json=body)
    assert r.status_code == 403
    assert bot["calls"] == []


def test_staff_resync_preview_and_apply_for_admin(client, fake_db, bot, session_with):
    """Review Focus 5 : ``staff_roles`` changé → aperçu puis application, journalisés."""
    fake_db.on("from user_voice_data", {"name": "Admin"})
    session_with(is_admin=True)
    r = client.post("/admin/channels/staff-resync/preview")
    assert r.status_code == 200 and r.json()["channels"][0]["id"] == "30"
    assert bot["calls"][-1][2] == {"actor_id": "1"}
    r = client.post("/admin/channels/staff-resync/apply", json={"token": "tok-1"})
    assert r.status_code == 200
    assert bot["calls"][-1][:3] == ("post", "/discord/channels/staff-resync/apply",
                                    {"actor_id": "1", "token": "tok-1", "actor_name": "Admin"})
    [row] = _audit(fake_db)
    assert (row["kind"], row["action"], row["success"]) == ("permission", "channel_staff_resync", True)
    assert row["details"]["changes"] == [{"id": "30", "name": "staff-only", "changes": CHANGES}]


def test_staff_resync_stale_is_409(client, fake_db, bot, session_with):
    session_with(is_admin=True)
    bot["token"] = "tok-2"
    r = client.post("/admin/channels/staff-resync/apply", json={"token": "tok-1"})
    assert r.status_code == 409 and r.json()["detail"] == STALE
    assert "/discord/channels/staff-resync/apply" not in _paths(bot)


def test_staff_resync_without_staff_roles_422_relayed(client, fake_db, bot, session_with):
    session_with(is_admin=True)
    bot["errors"][("post", "/discord/channels/staff-resync/preview")] = HTTPException(
        422, "Aucun rôle staff n'est réglé (staff_roles)")
    r = client.post("/admin/channels/staff-resync/preview")
    assert r.status_code == 422 and "staff_roles" in r.json()["detail"]


# ── Aucun nom de salon invisible dans les réponses ──────────────────────────

@pytest.mark.parametrize("method,path,body", [
    ("patch", "/admin/channels/30", {"name": "y"}),
    ("delete", "/admin/channels/30", {"confirm_name": "faux"}),
    ("post", "/admin/channels/30/template/preview", {"template": "public"}),
    ("post", "/admin/channels/30/template/apply", {"template": "public", "token": "tok-1"}),
])
def test_invisible_channel_is_404_without_name(mod, client, bot, method, path, body):
    r = client.request(method.upper(), path, json=body)
    assert r.status_code == 404 and r.json()["detail"] == "Salon introuvable"
    assert "staff-only" not in r.text
    assert _writes(bot) == [] and not any(p.endswith("/preview") for p in _paths(bot))


def test_missing_channel_gives_same_404(mod, client, bot):
    r = client.request("DELETE", "/admin/channels/999", json={"confirm_name": "x"})
    assert r.status_code == 404 and r.json()["detail"] == "Salon introuvable"


def test_staff_resync_error_relayed_without_name(mod, client, bot, session_with):
    session_with({"channels.manage"}, is_admin=True)
    bot["errors"][("post", "/discord/channels/staff-resync/preview")] = HTTPException(
        403, "Vous ne voyez pas l'un des salons concernés dans Discord.")
    r = client.post("/admin/channels/staff-resync/preview")
    assert r.status_code == 403 and "staff-only" not in r.text


# ── Catégorie parente invisible ou inexistante : 404 uniforme (I1) ──────────

HIDDEN_CAT_TREE = [_ch("10", "general"), _ch("40", "Secrets", "category", visible=False),
                   _ch("21", "fortnite", parent="20"), _ch("20", "Jeux", "category")]


@pytest.mark.parametrize("parent", ["40", "999", "10"])  # cachée, inexistante, pas une catégorie
def test_create_in_unseen_or_missing_category_is_uniform_404(client, mod, bot, monkeypatch, parent):
    monkeypatch.setattr(sys.modules[__name__], "TREE", HIDDEN_CAT_TREE)
    r = client.post("/admin/channels", json={"name": "x", "type": "text", "parent_id": parent})
    assert r.status_code == 404 and r.json()["detail"] == "Catégorie introuvable"
    assert "Secrets" not in r.text and _writes(bot) == []


@pytest.mark.parametrize("parent", ["40", "999"])
def test_move_into_unseen_or_missing_category_is_uniform_404(client, mod, bot, monkeypatch, parent):
    monkeypatch.setattr(sys.modules[__name__], "TREE", HIDDEN_CAT_TREE)
    r = client.patch("/admin/channels/10", json={"parent_id": parent})
    assert r.status_code == 404 and r.json()["detail"] == "Catégorie introuvable"
    assert "Secrets" not in r.text and _writes(bot) == []


def test_move_into_visible_category_and_owner_exemption(client, mod, bot, monkeypatch):
    monkeypatch.setattr(sys.modules[__name__], "TREE", HIDDEN_CAT_TREE)
    assert client.patch("/admin/channels/10", json={"parent_id": "20"}).status_code == 200
    bot["ranks"]["1"] = {"top_position": 0, "is_owner": True}
    assert client.patch("/admin/channels/10", json={"parent_id": "40"}).status_code == 200
    assert client.post("/admin/channels", json={"name": "x", "type": "text", "parent_id": "40"}).status_code == 200
