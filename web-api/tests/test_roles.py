"""Rôles, rôles des membres, lots et règles automatiques (étape 3, tâche 4)."""
import json

import pytest
from fastapi import HTTPException

from limiter import limiter
from permissions import PERMISSIONS
from routes import admin
from routes.roles import find_conflicts

# Rôles tels que renvoyés par le bot (/discord/roles), position décroissante.
ROLES = [
    {"id": "900", "name": "Hermes", "color": 0, "position": 20, "managed": True, "members": 1, "below_bot": False},
    {"id": "800", "name": "Fondateur", "color": 1, "position": 15, "managed": False, "members": 1, "below_bot": False},
    {"id": "500", "name": "Chef", "color": 1, "position": 10, "managed": False, "members": 2, "below_bot": True},
    {"id": "400", "name": "Modo", "color": 2, "position": 5, "managed": False, "members": 3, "below_bot": True},
    {"id": "300", "name": "Twitch", "color": 0, "position": 4, "managed": True, "members": 7, "below_bot": True},
    {"id": "200", "name": "Membre", "color": 3, "position": 1, "managed": False, "members": 37, "below_bot": True},
]

RULE_COLS = ("condition_type", "condition_value", "role_id", "create_role_name", "create_role_color",
             "remove_when_lost", "exclusive_group", "active", "reconcile")


@pytest.fixture
def bot(monkeypatch):
    """Bot factice : rôles, rangs (``ranks[discord_id]``), réponses et erreurs programmables."""
    state = {
        "roles": [dict(r) for r in ROLES],
        "ranks": {"1": {"top_position": 5, "is_owner": False, "role_ids": []}},
        "calls": [],
        "errors": {},  # (méthode, chemin) → HTTPException levée
        "jobs": {},
    }

    async def fake_bot(method, path, **kwargs):
        state["calls"].append((method, path, kwargs.get("json")))
        if (method, path) in state["errors"]:
            raise state["errors"][(method, path)]
        if path == "/discord/roles" and method == "get":
            return {"roles": state["roles"]}
        if path.startswith("/discord/members/") and path.endswith("/rank"):
            uid = path.split("/")[3]
            if uid not in state["ranks"]:
                raise HTTPException(status_code=404, detail="Member not found")
            return state["ranks"][uid]
        if path == "/discord/roles" and method == "post":
            body = kwargs["json"]
            return {"id": "777", "name": body["name"], "color": body["color"], "position": 1,
                    "managed": False, "members": 0, "below_bot": True}
        if path.startswith("/discord/roles/") and path.endswith("/bulk"):
            return {"job_id": "job-bulk"}
        if path.startswith("/discord/roles/") and method == "patch":
            role = next(r for r in state["roles"] if r["id"] == path.split("/")[3])
            return {**role, **{k: v for k, v in kwargs["json"].items() if k != "actor_name"}}
        if path.startswith("/discord/roles/") and method == "delete":
            return {"ok": True}
        if path.startswith("/discord/members/") and "/roles/" in path:
            return {"ok": True}
        if path.startswith("/discord/jobs/"):
            job = state["jobs"].get(path.split("/")[3])
            if job is None:
                raise HTTPException(status_code=404, detail="Travail inconnu (bot redémarré ou travail expiré)")
            return job
        if path == "/role-rules/reload":
            return {"ok": True}
        if path.endswith("/preview"):
            return {"gain": [{"id": "11", "name": "Alice"}], "lose": [], "missing_role": False}
        if path.endswith("/apply"):
            return {"job_id": "job-apply"}
        raise AssertionError(f"appel bot inattendu : {method} {path}")

    monkeypatch.setattr(admin, "_bot", fake_bot)
    monkeypatch.setattr(limiter, "enabled", False)
    return state


@pytest.fixture
def rules(fake_db):
    """Table role_rules en mémoire, branchée sur ``fake_db``."""
    store: dict[int, dict] = {}
    counter = {"next": 1}

    def add(**fields):
        rid = counter["next"]
        counter["next"] += 1
        row = {"id": rid, "condition_type": "voice_hours", "condition_value": "100", "role_id": None,
               "create_role_name": None, "create_role_color": None, "remove_when_lost": False,
               "exclusive_group": None, "active": True, "reconcile": False, **fields}
        store[rid] = row
        return row

    def insert(sql, *args):
        return add(**dict(zip(RULE_COLS, args[:len(RULE_COLS)])))

    def update(sql, rid, *args):
        if rid not in store:
            return None
        store[rid].update(dict(zip(RULE_COLS + ("previous_role_id",), args)))
        return store[rid]

    def delete(sql, rid):
        return {"id": rid} if store.pop(rid, None) else None

    fake_db.on("left join achievements", lambda sql: [
        {**r, "achievement_name": "Moulin à paroles" if r["condition_type"] == "achievement" else None}
        for r in sorted(store.values(), key=lambda r: r["id"])
    ])
    fake_db.on("insert into role_rules", insert)
    fake_db.on("update role_rules", update)
    fake_db.on("delete from role_rules", delete)
    fake_db.on("from role_rules where id", lambda sql, rid: store.get(rid))
    fake_db.on("from role_rules order by id", lambda sql: sorted(store.values(), key=lambda r: r["id"]))
    fake_db.on("from achievements where id", lambda sql, aid: 1 if aid == 3 else None)
    fake_db.on("from grades where slug", lambda sql, slug: 1 if slug == "veteran" else None)
    return {"store": store, "add": add}


def _audit(fake_db):
    """Lignes d'audit écrites : dicts (kind, action, actor_id, target_id, target_name, details, success)."""
    rows = []
    for method, sql, args in fake_db.calls:
        if method == "execute" and "insert into audit_events" in sql.lower():
            kind, action, source, actor_id, _name, target_id, target_name, details, success = args
            assert source == "site"
            rows.append({"kind": kind, "action": action, "actor_id": actor_id, "target_id": target_id,
                         "target_name": target_name, "details": json.loads(details), "success": success})
    return rows


def _writes(bot):
    return [c for c in bot["calls"] if c[0] != "get"]


# ── find_conflicts (portage de bot/utils/role_rules.py, Ruling R1) ──────────

def test_find_conflicts_same_role_with_remove_when_lost():
    rules = [
        {"id": 1, "role_id": 10, "active": True, "remove_when_lost": True},
        {"id": 2, "role_id": 10, "active": True, "remove_when_lost": False},
    ]
    assert len(find_conflicts(rules)) == 1


def test_find_conflicts_ignores_inactive_and_harmless_duplicates():
    assert find_conflicts([
        {"id": 1, "role_id": 10, "active": True, "remove_when_lost": True},
        {"id": 2, "role_id": 10, "active": False, "remove_when_lost": False},
    ]) == []
    assert find_conflicts([
        {"id": 1, "role_id": 10, "active": True, "remove_when_lost": False},
        {"id": 2, "role_id": 10, "active": True, "remove_when_lost": False},
    ]) == []
    assert find_conflicts([
        {"id": 1, "role_id": None, "active": True, "remove_when_lost": True},
        {"id": 2, "role_id": None, "active": True, "remove_when_lost": True},
    ]) == []


# ── GET /admin/roles ────────────────────────────────────────────────────────

def test_list_roles_requires_a_role_right(client, fake_db, bot, session_with):
    session_with(set(PERMISSIONS) - {"roles.manage", "members.roles"})
    r = client.get("/admin/roles")
    assert r.status_code == 403


def test_list_roles_marks_editable(client, fake_db, bot, session_with):
    session_with({"members.roles"})
    r = client.get("/admin/roles")
    assert r.status_code == 200
    by_id = {role["id"]: role for role in r.json()["roles"]}
    assert by_id["900"]["editable"] is False  # managed et au-dessus du bot
    assert by_id["800"]["editable"] is False  # au-dessus du bot
    assert by_id["500"]["editable"] is False  # au-dessus de l'acteur (5)
    assert by_id["400"]["editable"] is False  # au niveau de l'acteur
    assert by_id["300"]["editable"] is False  # managed
    assert by_id["200"] == {**ROLES[5], "editable": True}
    assert r.json()["actor"]["top_position"] == 5


def test_list_roles_owner_edits_everything_the_bot_can(client, fake_db, bot, session_with):
    bot["ranks"]["1"] = {"top_position": 0, "is_owner": True, "role_ids": []}
    session_with({"roles.manage"})
    editable = {role["id"] for role in client.get("/admin/roles").json()["roles"] if role["editable"]}
    assert editable == {"500", "400", "200"}


# ── POST/PATCH/DELETE /admin/roles ──────────────────────────────────────────

def test_create_role_requires_roles_manage(client, fake_db, bot, session_with):
    session_with({"members.roles"})
    r = client.post("/admin/roles", json={"name": "Fortnite"})
    assert r.status_code == 403
    assert _writes(bot) == []


@pytest.mark.parametrize("body", [
    {"name": ""}, {"name": "   "}, {"name": "x" * 101},
    {"name": "Ok", "color": -1}, {"name": "Ok", "color": 0x1000000},
])
def test_create_role_validation_is_422(client, fake_db, bot, session_with, body):
    session_with({"roles.manage"})
    r = client.post("/admin/roles", json=body)
    assert r.status_code == 422
    assert _writes(bot) == []


def test_create_role_calls_bot_and_logs(client, fake_db, bot, session_with):
    session_with({"roles.manage"})
    r = client.post("/admin/roles", json={"name": "Fortnite", "color": 0xFF0000})
    assert r.status_code == 200
    assert r.json()["id"] == "777"
    assert ("post", "/discord/roles", {"name": "Fortnite", "color": 0xFF0000, "hoist": False,
                                       "mentionable": False, "actor_name": "1"}) in bot["calls"]
    (row,) = _audit(fake_db)
    assert row["kind"] == "role" and row["action"] == "role_create" and row["success"] is True
    assert row["target_id"] == 777 and row["target_name"] == "Fortnite"


def test_create_role_actor_without_room_below_is_403(client, fake_db, bot, session_with):
    bot["ranks"]["1"] = {"top_position": 1, "is_owner": False, "role_ids": []}
    session_with({"roles.manage"})
    r = client.post("/admin/roles", json={"name": "Fortnite"})
    assert r.status_code == 403
    assert _writes(bot) == []


def test_update_role_at_actor_level_is_403(client, fake_db, bot, session_with):
    session_with({"roles.manage"})
    r = client.patch("/admin/roles/400", json={"name": "Modérateur"})
    assert r.status_code == 403
    assert "au niveau du vôtre ou au-dessus" in r.json()["detail"]
    assert _writes(bot) == []


def test_update_role_owner_is_exempt(client, fake_db, bot, session_with):
    bot["ranks"]["1"] = {"top_position": 0, "is_owner": True, "role_ids": []}
    session_with({"roles.manage"})
    r = client.patch("/admin/roles/500", json={"name": "Chefs"})
    assert r.status_code == 200
    assert ("patch", "/discord/roles/500", {"name": "Chefs", "actor_name": "1"}) in bot["calls"]
    (row,) = _audit(fake_db)
    assert row["action"] == "role_update" and row["details"]["after"] == {"name": "Chefs"}
    assert row["details"]["before"] == {"name": "Chef"}


def test_update_role_moving_it_to_actor_level_is_403(client, fake_db, bot, session_with):
    session_with({"roles.manage"})
    r = client.patch("/admin/roles/200", json={"position": 5})
    assert r.status_code == 403
    assert _writes(bot) == []


def test_update_role_validation_and_managed(client, fake_db, bot, session_with):
    session_with({"roles.manage"})
    assert client.patch("/admin/roles/200", json={"name": ""}).status_code == 422
    assert client.patch("/admin/roles/200", json={"color": 0x1000000}).status_code == 422
    r = client.patch("/admin/roles/300", json={"name": "Twitch 2"})
    assert r.status_code == 403 and "intégration" in r.json()["detail"]
    assert client.patch("/admin/roles/123", json={"name": "X"}).status_code == 404
    assert _writes(bot) == []


def test_delete_role_with_stale_count_is_409(client, fake_db, bot, session_with):
    session_with({"roles.manage"})
    r = client.request("DELETE", "/admin/roles/200", json={"confirm_members": 36})
    assert r.status_code == 409
    assert "le nombre a changé" in r.json()["detail"].lower()
    assert _writes(bot) == []


def test_delete_role_with_right_count(client, fake_db, bot, session_with):
    session_with({"roles.manage"})
    r = client.request("DELETE", "/admin/roles/200", json={"confirm_members": 37})
    assert r.status_code == 200
    assert ("delete", "/discord/roles/200", {"actor_name": "1"}) in bot["calls"]
    (row,) = _audit(fake_db)
    assert row["kind"] == "role" and row["action"] == "role_delete"
    assert row["target_name"] == "Membre" and row["details"]["members"] == 37


def test_delete_role_bot_failure_is_logged(client, fake_db, bot, session_with):
    bot["errors"][("delete", "/discord/roles/200")] = HTTPException(status_code=403, detail="Permission refusée — x")
    session_with({"roles.manage"})
    r = client.request("DELETE", "/admin/roles/200", json={"confirm_members": 37})
    assert r.status_code == 403
    (row,) = _audit(fake_db)
    assert row["success"] is False and row["details"]["error"] == "Permission refusée — x"


# ── Rôles d'un membre ───────────────────────────────────────────────────────

def test_member_role_requires_members_roles(client, fake_db, bot, session_with):
    session_with({"roles.manage"})
    assert client.post("/admin/members/42/roles/200").status_code == 403
    assert client.delete("/admin/members/42/roles/200").status_code == 403
    assert _writes(bot) == []


def test_member_role_above_actor_is_403(client, fake_db, bot, session_with):
    session_with({"members.roles"})
    assert client.post("/admin/members/42/roles/500").status_code == 403
    assert _writes(bot) == []


def test_member_role_add_and_remove(client, fake_db, bot, session_with):
    session_with({"members.roles"})
    assert client.post("/admin/members/42/roles/200").json() == {"ok": True}
    assert client.delete("/admin/members/42/roles/200").json() == {"ok": True}
    assert ("post", "/discord/members/42/roles/200", {"actor_name": "1"}) in bot["calls"]
    assert ("delete", "/discord/members/42/roles/200", {"actor_name": "1"}) in bot["calls"]
    add, remove = _audit(fake_db)
    assert add["kind"] == "member_role" and add["action"] == "member_role_add"
    assert add["target_id"] == 42 and add["details"]["role"] == "Membre"
    assert remove["action"] == "member_role_remove"


# ── Lots ────────────────────────────────────────────────────────────────────

def test_bulk_with_stale_count_is_409(client, fake_db, bot, session_with):
    session_with({"members.roles"})
    r = client.post("/admin/roles/200/bulk",
                    json={"action": "add", "user_ids": ["1", "2", "2"], "confirm_count": 3})
    assert r.status_code == 409
    r = client.post("/admin/roles/200/bulk", json={"action": "add", "from_role_id": "400", "confirm_count": 2})
    assert r.status_code == 409
    assert _writes(bot) == []


def test_bulk_needs_exactly_one_source(client, fake_db, bot, session_with):
    session_with({"members.roles"})
    both = {"action": "add", "user_ids": ["1"], "from_role_id": "400", "confirm_count": 1}
    assert client.post("/admin/roles/200/bulk", json=both).status_code == 422
    assert client.post("/admin/roles/200/bulk", json={"action": "add", "confirm_count": 0}).status_code == 422
    assert client.post("/admin/roles/200/bulk",
                       json={"action": "swap", "user_ids": ["1"], "confirm_count": 1}).status_code == 422
    assert _writes(bot) == []


def test_bulk_above_actor_is_403(client, fake_db, bot, session_with):
    session_with({"members.roles"})
    r = client.post("/admin/roles/400/bulk", json={"action": "add", "user_ids": ["1"], "confirm_count": 1})
    assert r.status_code == 403
    assert _writes(bot) == []


def test_bulk_starts_a_job_and_logs(client, fake_db, bot, session_with):
    session_with({"members.roles"})
    r = client.post("/admin/roles/200/bulk", json={"action": "remove", "from_role_id": "400", "confirm_count": 3})
    assert r.status_code == 200 and r.json() == {"job_id": "job-bulk"}
    assert ("post", "/discord/roles/200/bulk", {"action": "remove", "user_ids": None, "from_role_id": "400",
                                                "actor_name": "1"}) in bot["calls"]
    (row,) = _audit(fake_db)
    assert row["kind"] == "member_role" and row["action"] == "member_role_bulk"
    assert row["details"] == {"role_id": "200", "role": "Membre", "action": "remove", "count": 3,
                              "from_role_id": "400", "job_id": "job-bulk"}


def test_bulk_bot_422_is_relayed_with_its_message(client, fake_db, bot, session_with):
    msg = "Le rôle source compte plus de 500 membres : découpez l'opération"
    bot["errors"][("post", "/discord/roles/200/bulk")] = HTTPException(status_code=422, detail=msg)
    session_with({"members.roles"})
    r = client.post("/admin/roles/200/bulk", json={"action": "add", "from_role_id": "400", "confirm_count": 3})
    assert r.status_code == 422 and r.json()["detail"] == msg
    (row,) = _audit(fake_db)
    assert row["success"] is False


def test_job_status_is_relayed(client, fake_db, bot, session_with):
    bot["jobs"]["j1"] = {"state": "done", "done": 3, "total": 3, "errors": 0}
    session_with({"members.roles"})
    assert client.get("/admin/jobs/j1").json() == {"state": "done", "done": 3, "total": 3, "errors": 0}
    assert client.get("/admin/jobs/nope").status_code == 404


def test_job_status_requires_a_role_right(client, fake_db, bot, session_with):
    session_with({"admin.view"})
    assert client.get("/admin/jobs/j1").status_code == 403


# ── Règles ──────────────────────────────────────────────────────────────────

def _reloads(bot):
    return [c for c in bot["calls"] if c[1] == "/role-rules/reload"]


def test_rules_require_roles_manage(client, fake_db, bot, rules, session_with):
    session_with({"members.roles"})
    assert client.get("/admin/role-rules").status_code == 403
    assert client.post("/admin/role-rules", json={"condition_type": "level", "condition_value": "5",
                                                  "role_id": "200"}).status_code == 403
    assert client.get("/admin/role-rules/1/preview").status_code == 403
    assert client.post("/admin/role-rules/1/apply", json={"confirm": True}).status_code == 403
    assert _writes(bot) == []


def test_list_rules_flags_missing_role(client, fake_db, bot, rules, session_with):
    rules["add"](condition_type="level", condition_value="5", role_id=200)
    rules["add"](condition_type="level", condition_value="10", role_id=12345)
    rules["add"](condition_type="achievement", condition_value="3", create_role_name="🏆 Moulin")
    session_with({"roles.manage"})
    body = client.get("/admin/role-rules").json()["rules"]
    assert [r["id"] for r in body] == [1, 2, 3]
    assert body[0]["role_id"] == "200" and body[0]["role_name"] == "Membre" and body[0]["missing_role"] is False
    assert body[1]["role_id"] == "12345" and body[1]["role_name"] is None and body[1]["missing_role"] is True
    assert body[2]["role_id"] is None and body[2]["missing_role"] is False
    assert body[2]["achievement_name"] == "Moulin à paroles"


@pytest.mark.parametrize("body, fragment", [
    ({"condition_type": "karma", "condition_value": "1", "role_id": "200"}, "condition"),
    ({"condition_type": "level", "condition_value": "abc", "role_id": "200"}, "nombre"),
    ({"condition_type": "level", "condition_value": "-1", "role_id": "200"}, "nombre"),
    ({"condition_type": "level", "condition_value": "2.5", "role_id": "200"}, "entier"),
    ({"condition_type": "grade", "condition_value": "inconnu", "role_id": "200"}, "grade"),
    ({"condition_type": "achievement", "condition_value": "99", "role_id": "200"}, "succès"),
    ({"condition_type": "level", "condition_value": "5"}, "rôle"),
    ({"condition_type": "level", "condition_value": "5", "create_role_name": "X"}, "succès"),
    ({"condition_type": "achievement", "condition_value": "3", "role_id": "200", "create_role_name": "X"}, "l'un ou l'autre"),
    ({"condition_type": "level", "condition_value": "5", "role_id": "300"}, "bot"),
    ({"condition_type": "level", "condition_value": "5", "role_id": "800"}, "bot"),
    ({"condition_type": "level", "condition_value": "5", "role_id": "12345"}, "introuvable"),
    ({"condition_type": "level", "condition_value": "5", "role_id": "200", "reconcile": True}, "aperçu"),
])
def test_create_rule_validation_is_422(client, fake_db, bot, rules, session_with, body, fragment):
    session_with({"roles.manage"})
    r = client.post("/admin/role-rules", json=body)
    assert r.status_code == 422, r.json()
    assert fragment in str(r.json()["detail"]).lower()
    assert rules["store"] == {}
    assert _writes(bot) == []


@pytest.mark.parametrize("body", [
    {"condition_type": "achievement", "condition_value": "3", "create_role_name": ""},
    {"condition_type": "achievement", "condition_value": "3", "create_role_name": "x" * 101},
    {"condition_type": "achievement", "condition_value": "3", "create_role_name": "X", "create_role_color": -1},
    {"condition_type": "level", "condition_value": "5", "role_id": "200", "exclusive_group": "g" * 51},
])
def test_create_rule_field_bounds_are_422(client, fake_db, bot, rules, session_with, body):
    session_with({"roles.manage"})
    assert client.post("/admin/role-rules", json=body).status_code == 422
    assert rules["store"] == {}


def test_create_rule_role_above_actor_is_403(client, fake_db, bot, rules, session_with):
    session_with({"roles.manage"})
    r = client.post("/admin/role-rules", json={"condition_type": "level", "condition_value": "5", "role_id": "500"})
    assert r.status_code == 403
    assert rules["store"] == {}


def test_create_rule_conflict_is_422(client, fake_db, bot, rules, session_with):
    rules["add"](condition_type="level", condition_value="5", role_id=200, remove_when_lost=True)
    session_with({"roles.manage"})
    r = client.post("/admin/role-rules", json={"condition_type": "messages", "condition_value": "100",
                                               "role_id": "200"})
    assert r.status_code == 422
    assert "Membre" in r.json()["detail"] and "contrediraient" in r.json()["detail"]
    assert len(rules["store"]) == 1


def test_create_rule_saves_reloads_and_logs(client, fake_db, bot, rules, session_with):
    session_with({"roles.manage"})
    r = client.post("/admin/role-rules", json={"condition_type": "grade", "condition_value": "veteran",
                                               "role_id": "200", "exclusive_group": "grades"})
    assert r.status_code == 200
    body = r.json()
    assert body["rule"]["id"] == 1 and body["rule"]["role_id"] == "200" and body["reloaded"] is True
    assert rules["store"][1]["role_id"] == 200 and rules["store"][1]["reconcile"] is False
    assert len(_reloads(bot)) == 1
    (row,) = _audit(fake_db)
    assert row["kind"] == "setting" and row["action"] == "role_rule_create"
    assert row["details"]["rule_id"] == 1 and row["details"]["condition_type"] == "grade"


def test_create_rule_achievement_with_created_role(client, fake_db, bot, rules, session_with):
    session_with({"roles.manage"})
    r = client.post("/admin/role-rules", json={"condition_type": "achievement", "condition_value": "3",
                                               "create_role_name": "🏆 Moulin", "create_role_color": 0xFFAA00})
    assert r.status_code == 200
    assert rules["store"][1]["create_role_name"] == "🏆 Moulin" and rules["store"][1]["role_id"] is None


def test_write_succeeds_even_if_reload_fails(client, fake_db, bot, rules, session_with):
    bot["errors"][("post", "/role-rules/reload")] = HTTPException(status_code=503, detail="Moteur absent")
    session_with({"roles.manage"})
    r = client.post("/admin/role-rules", json={"condition_type": "level", "condition_value": "5", "role_id": "200"})
    assert r.status_code == 200 and r.json()["reloaded"] is False
    assert 1 in rules["store"]


def test_patch_reconcile_requires_preview(client, fake_db, bot, rules, session_with):
    rules["add"](condition_type="level", condition_value="5", role_id=200)
    session_with({"roles.manage"})
    r = client.patch("/admin/role-rules/1", json={"reconcile": True})
    assert r.status_code == 422 and "aperçu" in r.json()["detail"]
    assert rules["store"][1]["reconcile"] is False
    r = client.patch("/admin/role-rules/1", json={"reconcile": True, "preview_seen": True})
    assert r.status_code == 200
    assert rules["store"][1]["reconcile"] is True
    assert len(_reloads(bot)) == 1
    (row,) = _audit(fake_db)
    assert row["action"] == "role_rule_update" and row["details"]["changes"] == {"reconcile": True}


def test_patch_role_change_reports_previous_role(client, fake_db, bot, rules, session_with):
    rules["add"](condition_type="level", condition_value="5", role_id=200)
    bot["roles"].append({"id": "150", "name": "Nouveau", "color": 0, "position": 2, "managed": False,
                         "members": 0, "below_bot": True})
    session_with({"roles.manage"})
    r = client.patch("/admin/role-rules/1", json={"role_id": "150"})
    assert r.status_code == 200
    assert r.json()["previous_role"] == {"id": "200", "name": "Membre", "members": 37}
    assert r.json()["rule"]["role_id"] == "150"
    assert r.json()["rule"]["previous_role_id"] == "200"
    assert rules["store"][1]["previous_role_id"] == 200  # mémorisé pour apply
    # Sans changement de rôle : pas d'ancien rôle, mais l'ancien mémorisé reste.
    assert client.patch("/admin/role-rules/1", json={"active": False}).json()["previous_role"] is None
    assert rules["store"][1]["previous_role_id"] == 200


def test_patch_keeps_rule_with_missing_role_editable(client, fake_db, bot, rules, session_with):
    rules["add"](condition_type="level", condition_value="5", role_id=12345)
    session_with({"roles.manage"})
    r = client.patch("/admin/role-rules/1", json={"active": False})
    assert r.status_code == 200 and rules["store"][1]["active"] is False


def test_patch_creating_conflict_is_422(client, fake_db, bot, rules, session_with):
    rules["add"](condition_type="level", condition_value="5", role_id=200)
    rules["add"](condition_type="messages", condition_value="10", role_id=200)
    session_with({"roles.manage"})
    r = client.patch("/admin/role-rules/2", json={"remove_when_lost": True})
    assert r.status_code == 422
    assert rules["store"][2]["remove_when_lost"] is False


def test_patch_and_delete_unknown_rule_is_404(client, fake_db, bot, rules, session_with):
    session_with({"roles.manage"})
    assert client.patch("/admin/role-rules/9", json={"active": False}).status_code == 404
    assert client.delete("/admin/role-rules/9").status_code == 404
    assert _reloads(bot) == []


def test_delete_rule_reloads_and_logs(client, fake_db, bot, rules, session_with):
    rules["add"](condition_type="level", condition_value="5", role_id=200)
    session_with({"roles.manage"})
    r = client.delete("/admin/role-rules/1")
    assert r.status_code == 200 and r.json()["ok"] is True
    assert rules["store"] == {}
    assert len(_reloads(bot)) == 1
    (row,) = _audit(fake_db)
    assert row["kind"] == "setting" and row["action"] == "role_rule_delete" and row["details"]["rule_id"] == 1


def test_delete_rule_on_role_above_actor_is_403(client, fake_db, bot, rules, session_with):
    rules["add"](condition_type="level", condition_value="5", role_id=500)
    session_with({"roles.manage"})
    assert client.delete("/admin/role-rules/1").status_code == 403
    assert 1 in rules["store"]


def test_preview_is_relayed(client, fake_db, bot, rules, session_with):
    rules["add"](condition_type="level", condition_value="5", role_id=200)
    session_with({"roles.manage"})
    r = client.get("/admin/role-rules/1/preview")
    assert r.json() == {"gain": [{"id": "11", "name": "Alice"}], "lose": [], "missing_role": False}


def test_apply_requires_confirm(client, fake_db, bot, rules, session_with):
    rules["add"](condition_type="level", condition_value="5", role_id=200)
    session_with({"roles.manage"})
    assert client.post("/admin/role-rules/1/apply", json={"confirm": False}).status_code == 422
    assert client.post("/admin/role-rules/1/apply", json={}).status_code == 422
    assert _writes(bot) == []


def test_apply_unknown_rule_is_404(client, fake_db, bot, rules, session_with):
    session_with({"roles.manage"})
    assert client.post("/admin/role-rules/9/apply", json={"confirm": True}).status_code == 404


def test_apply_starts_job_and_logs(client, fake_db, bot, rules, session_with):
    rules["add"](condition_type="level", condition_value="5", role_id=200)
    session_with({"roles.manage"})
    r = client.post("/admin/role-rules/1/apply", json={"confirm": True, "remove_previous_role_id": None})
    assert r.status_code == 200
    assert r.json() == {"job_id": "job-apply", "remove_job_id": None, "remove_error": None}
    assert [c[1] for c in _writes(bot)] == ["/role-rules/1/apply"]
    (row,) = _audit(fake_db)
    assert row["kind"] == "setting" and row["action"] == "role_rule_apply"
    assert row["details"]["job_id"] == "job-apply"


def _rule_with_previous(rules, bot, previous_role_id=150):
    """Règle passée de l'ancien rôle ``previous_role_id`` au rôle 200 (« Membre »)."""
    rules["add"](condition_type="level", condition_value="5", role_id=200, previous_role_id=previous_role_id)
    bot["roles"].append({"id": "150", "name": "Ancien", "color": 0, "position": 2, "managed": False,
                         "members": 4, "below_bot": True})


def _apply_previous(client, role_id="150", count=4):
    return client.post("/admin/role-rules/1/apply", json={
        "confirm": True, "remove_previous_role_id": role_id, "confirm_previous_members": count,
    })


def test_apply_removes_previous_role_when_asked(client, fake_db, bot, rules, session_with):
    _rule_with_previous(rules, bot)
    session_with({"roles.manage", "members.roles"})
    r = _apply_previous(client)
    assert r.status_code == 200
    assert r.json() == {"job_id": "job-apply", "remove_job_id": "job-bulk", "remove_error": None}
    assert ("post", "/discord/roles/150/bulk", {"action": "remove", "user_ids": None, "from_role_id": "150",
                                                "actor_name": "1"}) in bot["calls"]
    (row,) = _audit(fake_db)
    assert row["details"]["remove_previous_role_id"] == "150" and row["details"]["remove_job_id"] == "job-bulk"
    assert row["details"]["previous_members"] == 4


def test_apply_previous_role_with_stale_count_is_409(client, fake_db, bot, rules, session_with):
    _rule_with_previous(rules, bot)
    session_with({"roles.manage", "members.roles"})
    r = _apply_previous(client, count=3)
    assert r.status_code == 409 and "4 membre(s)" in r.json()["detail"]
    missing = client.post("/admin/role-rules/1/apply", json={"confirm": True, "remove_previous_role_id": "150"})
    assert missing.status_code == 409
    assert _writes(bot) == []


def test_apply_previous_role_requires_members_roles(client, fake_db, bot, rules, session_with):
    _rule_with_previous(rules, bot)
    session_with({"roles.manage"})
    assert _apply_previous(client).status_code == 403
    assert _writes(bot) == []


def test_apply_previous_role_must_be_the_rules_old_role(client, fake_db, bot, rules, session_with):
    _rule_with_previous(rules, bot)
    bot["roles"].append({"id": "120", "name": "Autre", "color": 0, "position": 2, "managed": False,
                         "members": 9, "below_bot": True})
    session_with({"roles.manage", "members.roles"})
    r = _apply_previous(client, role_id="120", count=9)
    assert r.status_code == 422 and r.json()["detail"] == "Ce rôle n'est pas l'ancien rôle de la règle"
    assert _writes(bot) == []


def test_apply_previous_role_without_recorded_old_role_is_422(client, fake_db, bot, rules, session_with):
    _rule_with_previous(rules, bot, previous_role_id=None)
    session_with({"roles.manage", "members.roles"})
    assert _apply_previous(client).status_code == 422
    assert _writes(bot) == []


def test_apply_previous_role_checks(client, fake_db, bot, rules, session_with):
    rules["add"](condition_type="level", condition_value="5", role_id=200, previous_role_id=500)
    session_with({"roles.manage", "members.roles"})
    same = _apply_previous(client, role_id="200", count=37)
    assert same.status_code == 422
    above = _apply_previous(client, role_id="500", count=2)
    assert above.status_code == 403
    assert _writes(bot) == []


def test_apply_on_role_above_actor_is_403(client, fake_db, bot, rules, session_with):
    rules["add"](condition_type="level", condition_value="5", role_id=500)
    session_with({"roles.manage"})
    assert client.post("/admin/role-rules/1/apply", json={"confirm": True}).status_code == 403
    assert _writes(bot) == []


# ── C1 : « créer au premier déblocage » sous un nom de rôle existant ───────

def _achievement_rule(name):
    return {"condition_type": "achievement", "condition_value": "3", "create_role_name": name}


def test_create_rule_with_name_of_role_above_actor_is_403(client, fake_db, bot, rules, session_with):
    session_with({"roles.manage"})
    r = client.post("/admin/role-rules", json=_achievement_rule("Chef"))
    assert r.status_code == 403
    assert rules["store"] == {}


def test_create_rule_with_name_of_unmanageable_role_is_422(client, fake_db, bot, rules, session_with):
    bot["ranks"]["1"] = {"top_position": 0, "is_owner": True, "role_ids": []}
    session_with({"roles.manage"})
    r = client.post("/admin/role-rules", json=_achievement_rule("Fondateur"))
    assert r.status_code == 422 and "bot" in r.json()["detail"]
    assert rules["store"] == {}


def test_create_rule_with_name_of_role_owner_is_exempt(client, fake_db, bot, rules, session_with):
    bot["ranks"]["1"] = {"top_position": 0, "is_owner": True, "role_ids": []}
    session_with({"roles.manage"})
    assert client.post("/admin/role-rules", json=_achievement_rule("Chef")).status_code == 200


def test_create_rule_with_name_of_role_below_actor_is_allowed(client, fake_db, bot, rules, session_with):
    session_with({"roles.manage"})
    assert client.post("/admin/role-rules", json=_achievement_rule("Membre")).status_code == 200


def test_create_rule_with_new_name_needs_room_below_actor(client, fake_db, bot, rules, session_with):
    bot["ranks"]["1"] = {"top_position": 1, "is_owner": False, "role_ids": []}
    session_with({"roles.manage"})
    assert client.post("/admin/role-rules", json=_achievement_rule("🏆 Neuf")).status_code == 403
    assert rules["store"] == {}


def test_patch_rule_to_name_of_role_above_actor_is_403(client, fake_db, bot, rules, session_with):
    rules["add"](condition_type="achievement", condition_value="3", create_role_name="🏆 Moulin")
    session_with({"roles.manage"})
    r = client.patch("/admin/role-rules/1", json={"create_role_name": "Chef"})
    assert r.status_code == 403
    assert rules["store"][1]["create_role_name"] == "🏆 Moulin"


def test_patch_rule_to_name_of_role_owner_is_exempt(client, fake_db, bot, rules, session_with):
    rules["add"](condition_type="achievement", condition_value="3", create_role_name="🏆 Moulin")
    bot["ranks"]["1"] = {"top_position": 0, "is_owner": True, "role_ids": []}
    session_with({"roles.manage"})
    assert client.patch("/admin/role-rules/1", json={"create_role_name": "Chef"}).status_code == 200


def test_apply_unresolved_rule_named_like_role_above_actor_is_403(client, fake_db, bot, rules, session_with):
    rules["add"](condition_type="achievement", condition_value="3", create_role_name="Chef")
    session_with({"roles.manage"})
    assert client.post("/admin/role-rules/1/apply", json={"confirm": True}).status_code == 403
    assert _writes(bot) == []


# ── I1 : règle de succès résolue par le bot ────────────────────────────────

def test_patch_reconcile_on_resolved_achievement_rule(client, fake_db, bot, rules, session_with):
    # Le bot a renseigné role_id et vidé create_role_name/create_role_color.
    rules["add"](condition_type="achievement", condition_value="3", role_id=200)
    session_with({"roles.manage"})
    r = client.patch("/admin/role-rules/1", json={"reconcile": True, "preview_seen": True})
    assert r.status_code == 200, r.json()
    assert rules["store"][1]["reconcile"] is True
    assert client.patch("/admin/role-rules/1", json={"active": False}).status_code == 200


# ── I2 : groupes exclusifs ─────────────────────────────────────────────────

def test_create_rule_in_group_with_role_above_actor_is_403(client, fake_db, bot, rules, session_with):
    rules["add"](condition_type="messages", condition_value="10", role_id=500, exclusive_group="staff")
    session_with({"roles.manage"})
    r = client.post("/admin/role-rules", json={"condition_type": "messages", "condition_value": "1000",
                                               "role_id": "200", "exclusive_group": "staff"})
    assert r.status_code == 403
    assert len(rules["store"]) == 1


def test_patch_rule_into_group_with_role_above_actor_is_403(client, fake_db, bot, rules, session_with):
    rules["add"](condition_type="messages", condition_value="10", role_id=500, exclusive_group="staff")
    rules["add"](condition_type="messages", condition_value="1000", role_id=200)
    session_with({"roles.manage"})
    r = client.patch("/admin/role-rules/2", json={"exclusive_group": "staff"})
    assert r.status_code == 403
    assert rules["store"][2]["exclusive_group"] is None


def test_group_owner_is_exempt(client, fake_db, bot, rules, session_with):
    rules["add"](condition_type="messages", condition_value="10", role_id=500, exclusive_group="staff")
    bot["ranks"]["1"] = {"top_position": 0, "is_owner": True, "role_ids": []}
    session_with({"roles.manage"})
    r = client.post("/admin/role-rules", json={"condition_type": "messages", "condition_value": "1000",
                                               "role_id": "200", "exclusive_group": "staff"})
    assert r.status_code == 200


def test_group_below_actor_is_allowed(client, fake_db, bot, rules, session_with):
    bot["roles"].append({"id": "150", "name": "Bas", "color": 0, "position": 2, "managed": False,
                         "members": 0, "below_bot": True})
    rules["add"](condition_type="messages", condition_value="10", role_id=150, exclusive_group="staff")
    session_with({"roles.manage"})
    r = client.post("/admin/role-rules", json={"condition_type": "messages", "condition_value": "1000",
                                               "role_id": "200", "exclusive_group": "staff"})
    assert r.status_code == 200


def test_group_mixing_condition_types_is_422(client, fake_db, bot, rules, session_with):
    bot["ranks"]["1"] = {"top_position": 0, "is_owner": True, "role_ids": []}
    rules["add"](condition_type="level", condition_value="10", role_id=500, exclusive_group="staff")
    rules["add"](condition_type="level", condition_value="20", role_id=400, exclusive_group="staff")
    session_with({"roles.manage"})
    r = client.post("/admin/role-rules", json={"condition_type": "messages", "condition_value": "1000",
                                               "role_id": "200", "exclusive_group": "staff"})
    assert r.status_code == 422 and "groupe" in r.json()["detail"]
    r = client.patch("/admin/role-rules/2", json={"condition_type": "messages"})
    assert r.status_code == 422
    assert rules["store"][2]["condition_type"] == "level"


# ── I4 : changer la cible d'une règle appliquée la repasse en aperçu ───────

@pytest.mark.parametrize("change", [
    {"role_id": "150"}, {"condition_type": "messages"}, {"condition_value": "6"},
    {"exclusive_group": "paliers"},
])
def test_patch_target_or_condition_resets_reconcile(client, fake_db, bot, rules, session_with, change):
    rules["add"](condition_type="level", condition_value="5", role_id=200, reconcile=True)
    bot["roles"].append({"id": "150", "name": "Nouveau", "color": 0, "position": 2, "managed": False,
                         "members": 0, "below_bot": True})
    session_with({"roles.manage"})
    r = client.patch("/admin/role-rules/1", json=change)
    assert r.status_code == 200, r.json()
    assert rules["store"][1]["reconcile"] is False
    assert r.json()["rule"]["reconcile"] is False


def test_patch_other_fields_keeps_reconcile(client, fake_db, bot, rules, session_with):
    rules["add"](condition_type="level", condition_value="5", role_id=200, reconcile=True)
    session_with({"roles.manage"})
    assert client.patch("/admin/role-rules/1", json={"condition_value": "5", "active": False}).status_code == 200
    assert rules["store"][1]["reconcile"] is True


def test_patch_changing_target_cannot_keep_reconcile(client, fake_db, bot, rules, session_with):
    rules["add"](condition_type="level", condition_value="5", role_id=200, reconcile=True)
    session_with({"roles.manage"})
    r = client.patch("/admin/role-rules/1", json={"condition_value": "6", "reconcile": True, "preview_seen": True})
    assert r.status_code == 200
    assert rules["store"][1]["reconcile"] is False


# ── Mineurs T4 n°3 et n°2 ───────────────────────────────────────────────────

@pytest.mark.parametrize("value", ["²", "١", "9999999999", "3 "])
def test_achievement_value_must_be_small_ascii_integer(client, fake_db, bot, rules, session_with, value):
    session_with({"roles.manage"})
    r = client.post("/admin/role-rules", json={"condition_type": "achievement", "condition_value": value,
                                               "create_role_name": "X"})
    if value == "3 ":  # espaces retirés par le modèle : succès 3 valide
        assert r.status_code == 200
    else:
        assert r.status_code == 422 and "succès" in r.json()["detail"]


def test_apply_runs_rule_before_removing_previous_role(client, fake_db, bot, rules, session_with):
    _rule_with_previous(rules, bot)
    session_with({"roles.manage", "members.roles"})
    assert _apply_previous(client).status_code == 200
    assert [c[1] for c in _writes(bot)] == ["/role-rules/1/apply", "/discord/roles/150/bulk"]


def test_apply_failure_does_not_remove_previous_role(client, fake_db, bot, rules, session_with):
    _rule_with_previous(rules, bot)
    bot["errors"][("post", "/role-rules/1/apply")] = HTTPException(status_code=503, detail="Bot injoignable")
    session_with({"roles.manage", "members.roles"})
    assert _apply_previous(client).status_code == 503
    assert [c[1] for c in _writes(bot)] == ["/role-rules/1/apply"]


def test_apply_previous_role_over_500_members_is_422_before_anything(client, fake_db, bot, rules, session_with):
    _rule_with_previous(rules, bot)
    next(r for r in bot["roles"] if r["id"] == "150")["members"] = 501
    session_with({"roles.manage", "members.roles"})
    r = _apply_previous(client, count=501)
    assert r.status_code == 422 and "500" in r.json()["detail"]
    assert _writes(bot) == []


def test_apply_reports_previous_role_removal_failure(client, fake_db, bot, rules, session_with):
    _rule_with_previous(rules, bot)
    bot["errors"][("post", "/discord/roles/150/bulk")] = HTTPException(status_code=403, detail="Permission refusée")
    session_with({"roles.manage", "members.roles"})
    r = _apply_previous(client)
    assert r.status_code == 200
    assert r.json() == {"job_id": "job-apply", "remove_job_id": None, "remove_error": "Permission refusée"}
    failed, done = _audit(fake_db)
    assert failed["success"] is False and done["success"] is True


# ── R14 n°1 : rôles portés par un membre ───────────────────────────────────

def test_member_roles_requires_a_right(client, fake_db, bot, session_with):
    session_with(set(PERMISSIONS) - {"members.roles", "moderation.view"})
    assert client.get("/admin/members/42/roles").status_code == 403


def test_member_roles_lists_held_roles_with_editable(client, fake_db, bot, session_with):
    bot["ranks"]["42"] = {"top_position": 10, "is_owner": False, "role_ids": ["500", "200", "300"]}
    session_with({"members.roles"})
    r = client.get("/admin/members/42/roles")
    assert r.status_code == 200
    assert [(x["id"], x["name"], x["editable"]) for x in r.json()["roles"]] == [
        ("500", "Chef", False), ("300", "Twitch", False), ("200", "Membre", True),
    ]


def test_member_roles_without_members_roles_is_read_only(client, fake_db, bot, session_with):
    bot["ranks"]["42"] = {"top_position": 1, "is_owner": False, "role_ids": ["200"]}
    session_with({"moderation.view"})
    r = client.get("/admin/members/42/roles")
    assert r.status_code == 200
    assert [x["editable"] for x in r.json()["roles"]] == [False]


def test_member_roles_unknown_member_is_404(client, fake_db, bot, session_with):
    session_with({"members.roles"})
    assert client.get("/admin/members/43/roles").status_code == 404
