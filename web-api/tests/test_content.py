"""Tests des contenus éditables : jeux, pages, grades."""
from datetime import datetime, timezone

import pytest

import bot_client
import grades
from middleware import auth_middleware
from routes import content

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


@pytest.fixture(autouse=True)
def _bot_games(monkeypatch):
    """Bot factice pour les jeux : rien de pris, rechargement accepté (détails : test_games_admin.py)."""
    from routes import admin

    async def fake_bot(method, path, **kwargs):
        if path == "/games/taken":
            return {"commands": ["rang"], "emojis": ["⭐", "📺", "🎭"]}
        if path == "/games/reload":
            return {"ok": True}
        raise AssertionError(f"appel bot inattendu : {method} {path}")

    async def fake_bot_get(path, timeout=1.5):
        return None  # bot muet : statut des jeux inconnu

    monkeypatch.setattr(admin, "_bot", fake_bot)
    monkeypatch.setattr(content, "bot_get", fake_bot_get)


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

TABLE = [  # volontairement dans le désordre ; "old" est désactivé
    {"key": "lol", "name": "League of Legends", "color": "#F5A623", "image": "/media/a.png",
     "tagline": "Toxicité laissée au vestiaire.", "forum_channel_id": 555, "position": 3, "active": True},
    {"key": "old", "name": "Ancien", "color": "#000000", "image": None, "tagline": None,
     "forum_channel_id": None, "position": 1, "active": False},
    {"key": "war-dogs", "name": "War Dogs", "color": "#A12D2F", "image": None, "tagline": None,
     "forum_channel_id": None, "position": 2, "active": True},
]


def _site_games(fake_db):
    """``site_games`` simulée : le fake applique ``WHERE active`` et ``ORDER BY position`` demandés par le SQL."""
    def select(sql, *args):
        low = sql.lower()
        rows = [r for r in TABLE if r["active"] or "where active" not in low]
        return sorted(rows, key=lambda r: (r["position"], r["key"])) if "order by position" in low else rows

    fake_db.on("FROM site_games", select)


def test_games_ordered_by_position(client, fake_db, monkeypatch):
    _live(monkeypatch, {"game_players": {"lol": 12}})
    _site_games(fake_db)
    games = client.get("/games").json()["games"]
    assert [g["key"] for g in games] == ["war-dogs", "lol"]
    war, lol = games
    assert war["players"] is None and war["forum_url"] is None  # absent de /live, sans forum
    assert lol["players"] == 12
    assert lol["forum_url"] == "https://discord.com/channels/999/555"
    assert lol["image"] == "/media/a.png"
    assert lol["tagline"] == "Toxicité laissée au vestiaire." and war["tagline"] is None


def test_inactive_game_hidden(client, fake_db, monkeypatch):
    _live(monkeypatch, None)
    _site_games(fake_db)
    assert "old" not in [g["key"] for g in client.get("/games").json()["games"]]


def test_games_bot_down_players_null(client, fake_db, monkeypatch):
    _live(monkeypatch, None)
    _site_games(fake_db)
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
    _site_games(fake_db)
    assert client.get("/games").json()["games"][1]["forum_url"] is None


# ── Écriture des jeux ─────────────────────────────────────────────────────────

NEW = {"emoji": "🎯", "command_name": "apex"}

def test_create_game(client, fake_db, as_user):
    as_user()
    r = client.post("/admin/games", json={"key": "apex", "name": " Apex ", "color": "#aabbcc",
                                          "image": "/media/x.png", "forum_channel_id": "123", **NEW})
    assert r.status_code == 201
    args = _writes(fake_db)[0][2]
    assert args[:4] == ("apex", "Apex", "#AABBCC", "/media/x.png") and args[5] == 123


def test_create_game_duplicate_key_409(client, fake_db, as_user):
    as_user()
    fake_db.on("SELECT 1 FROM site_games", 1)
    r = client.post("/admin/games", json={"key": "lol", "name": "LoL", "color": "#FFFFFF", **NEW})
    assert r.status_code == 409 and not _writes(fake_db)


@pytest.mark.parametrize("body", [
    {"key": "Bad Key", "name": "x", "color": "#FFFFFF"},
    {"key": "ok\n", "name": "x", "color": "#FFFFFF"},
    {"key": "ok", "name": "x", "color": "#AABBCC\n"},
    {"key": "ok", "name": "x", "color": "#FFFFFF", "image": "/media/a.png\n"},
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
    # La CSP n'autorise aucun hôte d'images arbitraire : plus d'URL https.
    {"key": "ok", "name": "x", "color": "#FFFFFF", "image": "https://cdn.test/a.png"},
    {"key": "ok", "name": "x", "color": "#FFFFFF", "tagline": "a" * 121},
    {"key": "ok", "name": "x", "color": "#FFFFFF", "tagline": "deux\nlignes"},
    {"key": "ok", "name": "x", "color": "#FFFFFF", "tagline": "tab\tulation"},
    {"key": "ok", "name": "x", "color": "#FFFFFF", "tagline": 42},
    {"key": "ok", "name": "x", "color": "#FFFFFF", "forum_channel_id": "abc"},
    {"key": "ok", "name": "x", "color": "#FFFFFF", "forum_channel_id": 2 ** 63},
])
def test_create_game_rejects_bad_input(client, fake_db, as_user, body):
    as_user()
    assert client.post("/admin/games", json=body).status_code == 422
    assert not _writes(fake_db)


@pytest.mark.parametrize("image", [None, "", "/media/a-b_1.png"])
def test_game_image_accepted(client, fake_db, as_user, image):
    as_user()
    fake_db.on("SELECT 1 FROM site_games", None)
    r = client.post("/admin/games", json={"key": "ok", "name": "x", "color": "#FFFFFF", "image": image, **NEW})
    assert r.status_code == 201


def test_create_game_with_tagline(client, fake_db, as_user):
    as_user()
    r = client.post("/admin/games", json={"key": "apex", "name": "Apex", "color": "#AABBCC",
                                          "tagline": "  " + "a" * 120 + " ", **NEW})
    assert r.status_code == 201
    sql, args = _writes(fake_db)[0][1], _writes(fake_db)[0][2]
    assert "tagline" in sql and args[7] == "a" * 120  # 120 caractères inclus, espaces retirés


@pytest.mark.parametrize("tagline, stored", [("Le soutien, c'est un mode de vie.", "Le soutien, c'est un mode de vie."),
                                              ("   ", None), (None, None)])
def test_update_game_tagline(client, fake_db, as_user, tagline, stored):
    as_user()
    fake_db.on("SELECT key, name FROM site_games", {"key": "lol", "name": "LoL"})
    assert client.put("/admin/games/lol", json={"tagline": tagline}).status_code == 200
    sql, args = _writes(fake_db)[0][1], _writes(fake_db)[0][2]
    assert "tagline = $2" in sql and args == ("lol", stored)


def test_update_game_partial(client, fake_db, as_user):
    as_user()
    fake_db.on("SELECT key, name FROM site_games", {"key": "lol", "name": "LoL"})
    assert client.put("/admin/games/lol", json={"color": "#112233", "position": 4}).status_code == 200
    sql, args = _writes(fake_db)[0][1], _writes(fake_db)[0][2]
    assert "color = $2" in sql and "position = $3" in sql and args == ("lol", "#112233", 4)


def test_update_unknown_game_404(client, fake_db, as_user):
    as_user()
    assert client.put("/admin/games/nope", json={"name": "x"}).status_code == 404


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


def test_game_path_key_with_newline_rejected(client, fake_db, as_user):
    as_user()
    assert client.put("/admin/games/lol%0A", json={"name": "x"}).status_code == 422
    assert client.get("/pages/reglement%0A").status_code == 422


# ── Grades ────────────────────────────────────────────────────────────────────

def test_grade_update(client, fake_db, as_user):
    as_user()
    fake_db.on("UPDATE grades", 1)
    grades._cache = (1e12, [])  # un cache présent doit être vidé
    r = client.put("/admin/grades/caporal", json={"name": " Caporal ", "color": "#3bd16f", "level_min": 4})
    assert r.status_code == 200 and grades._cache is None
    assert fake_db.calls[-1][2] == ("caporal", "Caporal", "#3BD16F", 4)


def _levels(fake_db):
    """Niveaux de ``grades`` simulés : le fake applique ``slug <> $2`` quand le SQL le demande."""
    levels = {"recrue": 1, "caporal": 3, "sergent": 8}

    def taken(sql, level, *rest):
        others = {k: v for k, v in levels.items() if "slug <> $2" not in sql or k != rest[0]}
        return 1 if level in others.values() else None

    fake_db.on("SELECT 1 FROM grades", taken)
    fake_db.on("UPDATE grades", 1)


def test_grade_update_rejects_duplicate_level(client, fake_db, as_user):
    as_user()
    _levels(fake_db)
    r = client.put("/admin/grades/caporal", json={"name": "C", "color": "#3BD16F", "level_min": 8})
    assert r.status_code == 409 and not _writes(fake_db)


def test_grade_resave_same_level_ok(client, fake_db, as_user):
    as_user()
    _levels(fake_db)  # caporal garde son propre niveau 3 : pas un doublon
    r = client.put("/admin/grades/caporal", json={"name": "Caporal+", "color": "#3BD16F", "level_min": 3})
    assert r.status_code == 200 and any("update grades" in c[1].lower() for c in fake_db.calls)


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
    {"name": "n", "color": "#3BD16F\n", "level_min": 3},
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
    ("post", "/admin/games", {"key": "ok", "name": "x", "color": "#FFFFFF", "emoji": "🎯", "command_name": "ok"}),
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


# ── GET /admin/games ──────────────────────────────────────────────────────────

def test_admin_games_lists_inactive_with_editable_fields(client, fake_db, as_user):
    as_user()
    extra = {"emoji": None, "command_name": None, "lfg_cooldown": 3600, "provisioned": False, "archived": False}
    fake_db.on("FROM site_games", [
        {**TABLE[1], **extra, "discord_role_id": None},
        {**TABLE[0], **extra, "discord_role_id": 1234567890123456789},
    ])
    r = client.get("/admin/games")
    assert r.status_code == 200
    old, lol = r.json()["games"]
    assert old["key"] == "old" and old["active"] is False and old["discord_role_id"] is None
    # Identifiants Discord en chaîne : un nombre JS perdrait les derniers chiffres.
    assert lol["discord_role_id"] == "1234567890123456789" and lol["forum_channel_id"] == "555"
    assert lol["position"] == 3 and lol["tagline"] == "Toxicité laissée au vestiaire."
    sql = next(s for m, s, a in fake_db.calls if "site_games" in s)
    assert "where active" not in sql.lower()


def test_admin_games_requires_admin(client, fake_db, as_user):
    as_user(is_admin=False)
    assert client.get("/admin/games").status_code == 403
