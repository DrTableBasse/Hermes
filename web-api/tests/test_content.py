"""Tests des contenus éditables : jeux, pages, grades."""
from datetime import datetime, timezone

import pytest

import bot_client
import grades
from middleware import auth_middleware
from routes import content

GAMES = [
    {"key": "war-dogs", "name": "War Dogs", "color": "#A12D2F", "image": None, "forum_channel_id": None},
    {"key": "lol", "name": "League of Legends", "color": "#F5A623", "image": "/media/a.png",
     "forum_channel_id": 555},
]


@pytest.fixture(autouse=True)
def _fresh(monkeypatch):
    from limiter import limiter
    limiter.reset()
    bot_client.clear_cache()
    grades.clear_grades_cache()
    monkeypatch.setenv("GUILD_ID", "999")
    yield
    bot_client.clear_cache()
    grades.clear_grades_cache()


@pytest.fixture
def as_user(client, monkeypatch):
    def _as(discord_id="1", is_admin=True):
        async def fake_session(token):
            return {"sub": discord_id, "is_admin": is_admin, "is_redacteur": False}

        monkeypatch.setattr(auth_middleware, "_fetch_session", fake_session)
        client.cookies.set("better-auth.session_token", "tok")
    return _as


def _live(monkeypatch, payload):
    async def fake_bot_get(path, timeout=1.5):
        assert path == "/live"
        return payload

    monkeypatch.setattr(content, "bot_get", fake_bot_get)


def _writes(fake_db):
    return [c for c in fake_db.calls if c[0] == "execute"]


# ── GET /games ────────────────────────────────────────────────────────────────

def test_games_ordered_by_position(client, fake_db, monkeypatch):
    _live(monkeypatch, {"game_players": {"lol": 12}})
    fake_db.on("FROM site_games", GAMES)
    body = client.get("/games").json()
    assert [g["key"] for g in body["games"]] == ["war-dogs", "lol"]
    sql = [c for c in fake_db.calls if "site_games" in c[1]][0][1].lower()
    assert "order by position" in sql
    war, lol = body["games"]
    assert war["players"] is None and war["forum_url"] is None  # absent de /live, sans forum
    assert lol["players"] == 12
    assert lol["forum_url"] == "https://discord.com/channels/999/555"
    assert lol["image"] == "/media/a.png"


def test_inactive_game_hidden(client, fake_db, monkeypatch):
    _live(monkeypatch, None)
    fake_db.on("FROM site_games", GAMES[:1])
    client.get("/games")
    assert "where active" in [c for c in fake_db.calls if "site_games" in c[1]][0][1].lower()


def test_games_bot_down_players_null(client, fake_db, monkeypatch):
    _live(monkeypatch, None)
    fake_db.on("FROM site_games", GAMES)
    r = client.get("/games")
    assert r.status_code == 200 and [g["players"] for g in r.json()["games"]] == [None, None]


def test_games_db_down_never_500(client, fake_db, monkeypatch):
    _live(monkeypatch, None)

    def boom(sql, *args):
        raise RuntimeError("base en panne")

    fake_db.on("FROM site_games", boom)
    r = client.get("/games")
    assert r.status_code == 200 and r.json() == {"games": [], "stale": True}


def test_forum_url_null_without_guild(client, fake_db, monkeypatch):
    monkeypatch.delenv("GUILD_ID")
    _live(monkeypatch, None)
    fake_db.on("FROM site_games", GAMES)
    assert client.get("/games").json()["games"][1]["forum_url"] is None


# ── Écriture des jeux ─────────────────────────────────────────────────────────

def test_create_game(client, fake_db, as_user):
    as_user()
    r = client.post("/admin/games", json={"key": "apex", "name": " Apex ", "color": "#aabbcc",
                                          "image": "/media/x.png", "forum_channel_id": "123"})
    assert r.status_code == 201
    args = _writes(fake_db)[0][2]
    assert args[:4] == ("apex", "Apex", "#AABBCC", "/media/x.png") and args[5] == 123


def test_create_game_duplicate_key_409(client, fake_db, as_user):
    as_user()
    fake_db.on("SELECT 1 FROM site_games", 1)
    r = client.post("/admin/games", json={"key": "lol", "name": "LoL", "color": "#FFFFFF"})
    assert r.status_code == 409 and not _writes(fake_db)


@pytest.mark.parametrize("body", [
    {"key": "Bad Key", "name": "x", "color": "#FFFFFF"},
    {"key": "", "name": "x", "color": "#FFFFFF"},
    {"key": "a" * 33, "name": "x", "color": "#FFFFFF"},
    {"key": "ok", "name": "x", "color": "red"},
    {"key": "ok", "name": "x", "color": "#FFF"},
    {"key": "ok", "name": "", "color": "#FFFFFF"},
    {"key": "ok", "color": "#FFFFFF"},
    {"key": "ok", "name": "x", "color": "#FFFFFF", "image": "javascript:alert(1)"},
    {"key": "ok", "name": "x", "color": "#FFFFFF", "image": "http://insecure/a.png"},
    {"key": "ok", "name": "x", "color": "#FFFFFF", "image": "/media/../etc/passwd"},
    {"key": "ok", "name": "x", "color": "#FFFFFF", "image": "//evil.test/a.png"},
    {"key": "ok", "name": "x", "color": "#FFFFFF", "forum_channel_id": "abc"},
    {"key": "ok", "name": "x", "color": "#FFFFFF", "forum_channel_id": 2 ** 63},
])
def test_create_game_rejects_bad_input(client, fake_db, as_user, body):
    as_user()
    assert client.post("/admin/games", json=body).status_code == 422
    assert not _writes(fake_db)


@pytest.mark.parametrize("image", [None, "", "/media/a-b_1.png", "https://cdn.test/a.png"])
def test_game_image_accepted(client, fake_db, as_user, image):
    as_user()
    fake_db.on("SELECT 1 FROM site_games", None)
    r = client.post("/admin/games", json={"key": "ok", "name": "x", "color": "#FFFFFF", "image": image})
    assert r.status_code == 201


def test_update_game_partial(client, fake_db, as_user):
    as_user()
    fake_db.on("SELECT 1 FROM site_games", 1)
    assert client.put("/admin/games/lol", json={"color": "#112233", "position": 4}).status_code == 200
    sql, args = _writes(fake_db)[0][1], _writes(fake_db)[0][2]
    assert "color = $2" in sql and "position = $3" in sql and args == ("lol", "#112233", 4)


def test_update_unknown_game_404(client, fake_db, as_user):
    as_user()
    assert client.put("/admin/games/nope", json={"name": "x"}).status_code == 404


def test_delete_game_deactivates(client, fake_db, as_user):
    as_user()
    fake_db.on("UPDATE site_games", 1)
    assert client.delete("/admin/games/lol").status_code == 200
    assert "active = false" in fake_db.calls[-1][1].lower() and "delete" not in fake_db.calls[-1][1].lower()
    fake_db.rules.clear()
    assert client.delete("/admin/games/nope").status_code == 404


# ── Pages ─────────────────────────────────────────────────────────────────────

def test_page_unknown_404(client, fake_db):
    assert client.get("/pages/inconnue").status_code == 404


def test_page_empty_body_allowed(client, fake_db):
    fake_db.on("FROM site_pages", {"slug": "reglement", "title": "Règlement", "body_md": "", "updated_at": None})
    r = client.get("/pages/reglement")
    assert r.status_code == 200 and r.json()["body_md"] == "" and r.json()["updated_at"] is None


def test_page_returns_content(client, fake_db):
    when = datetime(2026, 11, 20, tzinfo=timezone.utc)
    fake_db.on("FROM site_pages", {"slug": "reglement", "title": "Règlement", "body_md": "# Règle 1", "updated_at": when})
    body = client.get("/pages/reglement").json()
    assert body["body_md"] == "# Règle 1" and body["updated_at"] == when.isoformat()


def test_page_update(client, fake_db, as_user):
    as_user("42")
    fake_db.on("UPDATE site_pages", 1)
    r = client.put("/admin/pages/reglement", json={"title": " Règlement ", "body_md": "<b>x</b>"})
    assert r.status_code == 200
    assert fake_db.calls[-1][2] == ("reglement", "Règlement", "<b>x</b>", 42)  # stocké brut


def test_page_update_unknown_404(client, fake_db, as_user):
    as_user()
    assert client.put("/admin/pages/inconnue", json={"title": "t", "body_md": ""}).status_code == 404


@pytest.mark.parametrize("body", [
    {"title": "", "body_md": ""}, {"title": "t"}, {"body_md": "x"},
    {"title": "t", "body_md": "x" * 50_001}, {"title": "a\nb", "body_md": ""}, {"title": "t", "body_md": 3},
])
def test_page_update_rejects_bad_input(client, fake_db, as_user, body):
    as_user()
    assert client.put("/admin/pages/reglement", json=body).status_code == 422
    assert not _writes(fake_db)


def test_page_body_limit_inclusive(client, fake_db, as_user):
    as_user()
    fake_db.on("UPDATE site_pages", 1)
    assert client.put("/admin/pages/reglement", json={"title": "t", "body_md": "x" * 50_000}).status_code == 200


# ── Grades ────────────────────────────────────────────────────────────────────

def test_grade_update(client, fake_db, as_user):
    as_user()
    fake_db.on("UPDATE grades", 1)
    grades._cache = (1e12, [])  # un cache présent doit être vidé
    r = client.put("/admin/grades/caporal", json={"name": " Caporal ", "color": "#3bd16f", "level_min": 4})
    assert r.status_code == 200 and grades._cache is None
    assert fake_db.calls[-1][2] == ("caporal", "Caporal", "#3BD16F", 4)


def test_grade_update_rejects_duplicate_level(client, fake_db, as_user):
    as_user()
    fake_db.on("SELECT 1 FROM grades", 1)
    r = client.put("/admin/grades/caporal", json={"name": "C", "color": "#3BD16F", "level_min": 8})
    assert r.status_code == 409 and not _writes(fake_db)


def test_grade_unique_violation_race_409(client, fake_db, as_user):
    import asyncpg
    as_user()

    def race(sql, *args):
        raise asyncpg.UniqueViolationError("doublon")

    fake_db.on("UPDATE grades", race)
    r = client.put("/admin/grades/caporal", json={"name": "C", "color": "#3BD16F", "level_min": 4})
    assert r.status_code == 409


def test_grade_recrue_must_stay_level_1(client, fake_db, as_user):
    as_user()
    fake_db.on("UPDATE grades", 1)
    assert client.put("/admin/grades/recrue", json={"name": "R", "color": "#9A97B8", "level_min": 2}).status_code == 422
    assert client.put("/admin/grades/recrue", json={"name": "R", "color": "#9A97B8", "level_min": 1}).status_code == 200


@pytest.mark.parametrize("body", [
    {"name": "", "color": "#FFFFFF", "level_min": 3}, {"name": "n", "color": "blue", "level_min": 3},
    {"name": "n", "color": "#FFFFFF", "level_min": 0}, {"name": "n", "color": "#FFFFFF", "level_min": "3"},
    {"name": "n", "color": "#FFFFFF", "level_min": True}, {"name": "n", "color": "#FFFFFF", "level_min": 1001},
    {"name": "a" * 41, "color": "#FFFFFF", "level_min": 3}, {"name": "n", "color": "#FFFFFF"},
])
def test_grade_update_rejects_bad_input(client, fake_db, as_user, body):
    as_user()
    assert client.put("/admin/grades/caporal", json=body).status_code == 422
    assert not _writes(fake_db)


def test_grade_unknown_404(client, fake_db, as_user):
    as_user()
    assert client.put("/admin/grades/nope", json={"name": "n", "color": "#FFFFFF", "level_min": 9}).status_code == 404


# ── Accès ─────────────────────────────────────────────────────────────────────

ADMIN_CALLS = [
    ("post", "/admin/games", {"key": "ok", "name": "x", "color": "#FFFFFF"}),
    ("put", "/admin/games/lol", {"name": "x"}),
    ("delete", "/admin/games/lol", None),
    ("put", "/admin/pages/reglement", {"title": "t", "body_md": ""}),
    ("put", "/admin/grades/caporal", {"name": "n", "color": "#FFFFFF", "level_min": 4}),
]


@pytest.mark.parametrize("method,url,body", ADMIN_CALLS)
def test_content_admin_only(client, fake_db, as_user, method, url, body):
    kwargs = {"json": body} if body is not None else {}
    assert getattr(client, method)(url, **kwargs).status_code == 401  # sans session
    as_user("2", is_admin=False)
    assert getattr(client, method)(url, **kwargs).status_code == 403
    assert not _writes(fake_db)
