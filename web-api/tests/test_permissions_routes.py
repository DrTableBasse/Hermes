"""Droits exigés route par route (étape 2, tâche 3).

Chaque ligne de ``CASES`` reprend la correspondance route → droit du plan : une session munie du
seul droit franchit le contrôle (pas de 403) ; une session munie de **tous les autres** droits
reçoit 403 « Droit requis : <libellé> ».
"""
import httpx
import pytest
from fastapi.testclient import TestClient

from limiter import limiter
from middleware.auth_middleware import has_permission, require_any_permission, require_permission
from permissions import PERMISSIONS

QUEST = {"title": "t", "quest_type": "messages", "target_value": 1}
WARN = {"user_id": "2", "reason": "r"}
GAME = {"key": "jeu", "name": "Jeu", "color": "#112233"}

# (méthode, chemin, droit, corps JSON)
CASES = [
    # admin.py
    ("get", "/admin/stats", "admin.view", None),
    ("get", "/admin/commands", "settings.manage", None),
    ("post", "/admin/commands/toggle", "settings.manage", {"command_name": "ping", "enabled": True}),
    ("post", "/admin/kick", "moderation.act", WARN),
    ("post", "/admin/ban", "moderation.act", WARN),
    ("post", "/admin/timeout", "moderation.act", {**WARN, "duration": 60}),
    ("post", "/admin/warns", "moderation.act", WARN),
    ("delete", "/admin/warns/1", "moderation.act", None),
    ("get", "/admin/warns", "moderation.view", None),
    ("get", "/admin/warns/2", "moderation.view", None),
    ("get", "/admin/users/search?q=ab", "moderation.view", None),
    ("get", "/admin/quest-templates", "quests.manage", None),
    ("post", "/admin/quest-templates", "quests.manage", QUEST),
    ("put", "/admin/quest-templates/1", "quests.manage", QUEST),
    ("delete", "/admin/quest-templates/1", "quests.manage", None),
    ("get", "/admin/quests/active", "quests.manage", None),
    ("post", "/admin/quests/deploy", "quests.manage", {"count": 1}),
    ("get", "/admin/analytics", "analytics.view", None),
    ("get", "/admin/gallery", "gallery.manage", None),
    ("patch", "/admin/gallery/1", "gallery.manage", {"hidden": True}),
    ("delete", "/admin/gallery/1", "gallery.manage", None),
    # settings.py (réglages et lecture Discord)
    ("get", "/admin/settings", "settings.manage", None),
    ("put", "/admin/settings/bump_role_threshold", "settings.manage", {"value": "5"}),
    ("post", "/admin/settings/ticket_category/create-channel", "settings.manage", None),
    # audit.py
    ("get", "/admin/audit", "moderation.view", None),
    ("get", "/admin/audit.csv", "moderation.view", None),
    ("get", "/admin/audit/facets", "moderation.view", None),
    # content.py
    ("get", "/admin/games", "games.manage", None),
    ("post", "/admin/games", "games.manage", GAME),
    ("put", "/admin/games/jeu", "games.manage", GAME),
    ("delete", "/admin/games/jeu", "games.manage", None),
    ("put", "/admin/pages/regles", "content.edit", {"title": "Règles", "body_md": "x"}),
    # grades.py, staff.py
    ("put", "/admin/grades/recrue", "content.edit", {"name": "Recrue", "color": "#112233", "level_min": 1}),
    ("put", "/admin/staff/2", "content.edit", {"motto": "x", "games": []}),
    # tickets.py
    ("get", "/tickets", "tickets.manage", None),
    ("get", "/tickets/1/transcript", "tickets.manage", None),
    # articles.py, tags.py, media.py
    ("post", "/articles", "articles.write", {"title": "T", "content": "c"}),
    ("put", "/articles/1", "articles.write", {"title": "T"}),
    ("delete", "/articles/1", "articles.write", None),
    ("post", "/tags", "articles.publish", {"name": "n"}),
    ("put", "/tags/1", "articles.publish", {"name": "n"}),
    ("delete", "/tags/1", "articles.publish", None),
    ("post", "/media/upload", "articles.write", None),
]


@pytest.fixture
def api(client, fake_db, monkeypatch):
    """Client qui renvoie les 500 au lieu de les lever, sans limite de débit ni bot joignable."""
    monkeypatch.setattr(limiter, "enabled", False)

    async def offline(self, *args, **kwargs):
        raise httpx.ConnectError("bot injoignable (test)")

    monkeypatch.setattr(httpx.AsyncClient, "send", offline)
    lenient = TestClient(client.app, raise_server_exceptions=False)
    lenient.cookies.set("better-auth.session_token", "tok")
    return lenient


def _call(api, method, path, body):
    kwargs = {"json": body} if body is not None else {}
    return getattr(api, method)(path, **kwargs)


def _case_id(case):
    return f"{case[0].upper()} {case[1]} → {case[2]}"


def test_table_covers_the_whole_catalogue_used():
    assert {perm for _, _, perm, _ in CASES} <= set(PERMISSIONS)


@pytest.mark.parametrize("method,path,perm,body", CASES, ids=[_case_id(c) for c in CASES])
def test_route_passes_with_only_its_right(api, session_with, method, path, perm, body):
    session_with({perm})
    r = _call(api, method, path, body)
    assert r.status_code != 403, r.text


@pytest.mark.parametrize("method,path,perm,body", CASES, ids=[_case_id(c) for c in CASES])
def test_route_refused_without_its_right(api, session_with, method, path, perm, body):
    session_with(set(PERMISSIONS) - {perm})
    r = _call(api, method, path, body)
    assert r.status_code == 403
    assert r.json()["detail"] == f"Droit requis : {PERMISSIONS[perm]}"


@pytest.mark.parametrize("method,path,perm,body", CASES, ids=[_case_id(c) for c in CASES])
def test_admin_passes_everywhere(api, session_with, method, path, perm, body):
    session_with((), is_admin=True)
    assert _call(api, method, path, body).status_code != 403


# ── Listes Discord (lecture seule, plusieurs droits) ─────────────────────────

DISCORD_LISTS = ["/admin/discord/channels", "/admin/discord/roles"]
DISCORD_RIGHTS = ["admin.view", "games.manage", "settings.manage", "permissions.manage"]


@pytest.mark.parametrize("path", DISCORD_LISTS)
@pytest.mark.parametrize("perm", DISCORD_RIGHTS)
def test_discord_lists_open_to_each_reader_right(api, session_with, path, perm):
    session_with({perm})
    assert api.get(path).status_code != 403


@pytest.mark.parametrize("path", DISCORD_LISTS)
def test_discord_lists_refused_with_other_rights(api, session_with, path):
    session_with(set(PERMISSIONS) - set(DISCORD_RIGHTS))
    r = api.get(path)
    assert r.status_code == 403
    assert r.json()["detail"] == "Droit requis : " + " ou ".join(PERMISSIONS[p] for p in DISCORD_RIGHTS)


@pytest.mark.parametrize("path", DISCORD_LISTS)
def test_discord_lists_refused_with_tickets_only(api, session_with, path):
    session_with({"tickets.manage"})
    assert api.get(path).status_code == 403


# ── Publication d'articles ──────────────────────────────────────────────────

def test_creating_published_article_needs_publish_right(api, session_with):
    session_with({"articles.write"})
    r = api.post("/articles", json={"title": "T", "content": "c", "published": True})
    assert r.status_code == 403
    assert r.json()["detail"] == f"Droit requis : {PERMISSIONS['articles.publish']}"
    session_with({"articles.write", "articles.publish"})
    r = api.post("/articles", json={"title": "T", "content": "c", "published": True})
    assert r.status_code != 403


def test_publishing_existing_article_needs_publish_right(api, session_with, fake_db):
    fake_db.on("SELECT * FROM articles WHERE id", {"id": 1, "author_id": 1, "published": False})
    session_with({"articles.write"})
    r = api.put("/articles/1", json={"published": True})
    assert r.status_code == 403
    assert r.json()["detail"] == f"Droit requis : {PERMISSIONS['articles.publish']}"
    assert api.put("/articles/1", json={"title": "T"}).status_code != 403
    session_with({"articles.write", "articles.publish"})
    assert api.put("/articles/1", json={"published": True}).status_code != 403


def test_author_rule_still_applies(api, session_with, fake_db):
    fake_db.on("SELECT * FROM articles WHERE id", {"id": 1, "author_id": 99, "published": False})
    session_with({"articles.write", "articles.publish"})
    assert api.delete("/articles/1").status_code == 403


# ── Fonctions d'accès ───────────────────────────────────────────────────────

def test_has_permission_rejects_unknown_key():
    with pytest.raises(ValueError):
        has_permission({"is_admin": True, "permissions": frozenset()}, "admin.voir")


def test_has_permission_admin_and_set():
    assert has_permission({"is_admin": True, "permissions": frozenset()}, "roles.manage")
    assert has_permission({"is_admin": False, "permissions": frozenset({"admin.view"})}, "admin.view")
    assert not has_permission({"is_admin": False, "permissions": frozenset()}, "admin.view")
    assert not has_permission(None, "admin.view")


def test_require_permission_message():
    with pytest.raises(Exception) as exc:
        require_permission({"is_admin": False, "permissions": frozenset()}, "tickets.manage")
    assert exc.value.status_code == 403
    assert exc.value.detail == "Droit requis : Gérer les tickets"


def test_require_any_permission_accepts_any_listed_right():
    user = {"is_admin": False, "permissions": frozenset({"games.manage"})}
    assert require_any_permission(user, "admin.view", "games.manage") is user
    admin = {"is_admin": True, "permissions": frozenset()}
    assert require_any_permission(admin, "admin.view") is admin


def test_require_any_permission_message_lists_labels():
    with pytest.raises(Exception) as exc:
        require_any_permission({"is_admin": False, "permissions": frozenset({"tickets.manage"})},
                               "admin.view", "games.manage")
    assert exc.value.status_code == 403
    assert exc.value.detail == (
        f"Droit requis : {PERMISSIONS['admin.view']} ou {PERMISSIONS['games.manage']}")


def test_require_any_permission_rejects_unknown_key_and_empty():
    with pytest.raises(ValueError):
        require_any_permission({"is_admin": True, "permissions": frozenset()}, "admin.voir")
    with pytest.raises(ValueError):
        require_any_permission({"is_admin": True, "permissions": frozenset()})


def test_session_reads_site_permissions(fake_db):
    import asyncio
    import middleware.auth_middleware as auth_mw

    fake_db.on('"sitePermissions"', {
        "discordId": "1", "isAdmin": False, "isRedacteur": False,
        "sitePermissions": ["moderation.view", "inconnu", "admin.view"],
    })
    user = asyncio.run(auth_mw._fetch_session("tok.sig"))
    assert user["permissions"] == frozenset({"moderation.view", "admin.view"})
    fake_db.rules.clear()
    fake_db.on('"sitePermissions"', {
        "discordId": "1", "isAdmin": False, "isRedacteur": False, "sitePermissions": None,
    })
    assert asyncio.run(auth_mw._fetch_session("tok"))["permissions"] == frozenset()


# ── /auth/me ────────────────────────────────────────────────────────────────

def test_auth_me_returns_sorted_permissions(api, session_with):
    session_with({"tickets.manage", "admin.view", "moderation.view"})
    body = api.get("/auth/me").json()
    assert body["permissions"] == ["admin.view", "moderation.view", "tickets.manage"]


def test_auth_me_admin_has_every_permission(api, session_with):
    session_with((), is_admin=True)
    assert api.get("/auth/me").json()["permissions"] == sorted(PERMISSIONS)


# ── Journal : contenu des messages (moderation.content) ─────────────────────

def _message_rows(sql, *args):
    from datetime import datetime, timezone
    base = {
        "occurred_at": datetime(2026, 11, 23, tzinfo=timezone.utc), "source": "discord",
        "actor_id": 5, "actor_name": "Bob", "target_id": None, "target_name": None,
        "channel_id": 7, "channel_name": "général", "success": True,
    }
    return [
        {**base, "id": 1, "kind": "message", "action": "delete",
         "details": {"message_id": 9, "content": "motsecret", "attachments": [], "embeds": 0}},
        {**base, "id": 2, "kind": "message", "action": "edit",
         "details": {"message_id": 9, "avant": {"content": "motsecret"}, "après": {"content": "b"}}},
        {**base, "id": 3, "kind": "message", "action": "bulk_delete",
         "details": {"count": 2, "messages": [{"content": "motsecret"}]}},
        {**base, "id": 4, "kind": "sanction", "action": "kick",
         "details": {"reason": "spam"}},
    ]


def test_audit_hides_message_text_without_content_right(api, session_with, fake_db):
    fake_db.on("SELECT COUNT(*)", 4)
    fake_db.on("FROM audit_events", _message_rows)
    session_with({"moderation.view"})
    r = api.get("/admin/audit")
    assert r.status_code == 200
    assert "motsecret" not in r.text
    events = {e["id"]: e["details"] for e in r.json()["events"]}
    assert events[1] == {"message_id": 9, "attachments": [], "embeds": 0}
    assert events[2] == {"message_id": 9}
    assert events[3] == {"count": 2}
    assert events[4] == {"reason": "spam"}
    csv = api.get("/admin/audit.csv")
    assert csv.status_code == 200 and "motsecret" not in csv.text


def test_audit_shows_message_text_with_content_right(api, session_with, fake_db):
    fake_db.on("SELECT COUNT(*)", 4)
    fake_db.on("FROM audit_events", _message_rows)
    session_with({"moderation.view", "moderation.content"})
    r = api.get("/admin/audit")
    assert "motsecret" in r.text
    assert r.json()["events"][0]["details"]["content"] == "motsecret"
    assert "motsecret" in api.get("/admin/audit.csv").text


def test_audit_search_skips_details_without_content_right(api, session_with, fake_db):
    session_with({"moderation.view"})
    assert api.get("/admin/audit?q=motsecret").status_code == 200
    assert api.get("/admin/audit.csv?q=motsecret").status_code == 200
    sqls = [sql for _, sql, args in fake_db.calls if "audit_events" in sql and "%motsecret%" in args]
    assert sqls and all("details" not in sql.split("FROM audit_events")[1].split("ORDER BY")[0]
                        for sql in sqls)


def test_audit_search_covers_details_with_content_right(api, session_with, fake_db):
    session_with({"moderation.view", "moderation.content"})
    api.get("/admin/audit?q=motsecret")
    sqls = [sql for _, sql, args in fake_db.calls if "%motsecret%" in args]
    assert sqls and all("details::text ILIKE" in sql for sql in sqls)
