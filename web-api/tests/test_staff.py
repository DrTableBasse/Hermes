"""Tests de l'état-major : GET /staff, PUT /staff/me, PUT /admin/staff/{id}."""
import pytest

import bot_client
from middleware import auth_middleware
from routes import staff

BOT_STAFF = [
    {"id": "1", "name": "Chef", "avatar": "http://a/1.png", "role": "Administration"},
    {"id": "2", "name": "Modo", "avatar": "http://a/2.png", "role": "Modération"},
]


@pytest.fixture(autouse=True)
def _fresh(monkeypatch):
    from limiter import limiter
    limiter.reset()  # PUT limites a 20/min : le volume de tests depasserait la limite
    monkeypatch.setattr(staff, "_last_raw", None)
    bot_client.clear_cache()
    yield
    bot_client.clear_cache()


def _bot(monkeypatch, payload):
    async def fake_bot_get(path, timeout=1.5):
        assert path == "/staff"
        return payload

    monkeypatch.setattr(staff, "bot_get", fake_bot_get)




@pytest.fixture(autouse=True)
def _site_games(fake_db):
    """Jeux actifs connus de ``site_games`` (la vérification filtre sur ``key = ANY``)."""
    active = {"dbd", "lol", "minecraft"}
    fake_db.on("FROM site_games", lambda sql, keys: [{"key": k} for k in keys if k in active])


@pytest.fixture
def as_user(client, monkeypatch):
    def _as(discord_id, is_admin=False):
        async def fake_session(token):
            return {"sub": discord_id, "is_admin": is_admin, "is_redacteur": False}

        monkeypatch.setattr(auth_middleware, "_fetch_session", fake_session)
        client.cookies.set("better-auth.session_token", "tok")
    return _as


def test_staff_merge_profile(client, fake_db, monkeypatch):
    _bot(monkeypatch, BOT_STAFF)
    fake_db.on("FROM staff_profiles", [{"user_id": 1, "motto": "Tout schuss", "games": ["Valorant"]}])
    fake_db.on("FROM user_xp", [{"user_id": 1, "current_level": 30}, {"user_id": 2, "current_level": None}])
    body = client.get("/staff").json()
    assert "stale" not in body
    chef, modo = body["staff"]
    assert chef["id"] == "1" and chef["role"] == "Administration"
    assert chef["motto"] == "Tout schuss" and chef["games"] == ["Valorant"]
    assert chef["level"] == 30 and chef["grade"]["slug"] == "colonel"
    assert modo["motto"] is None and modo["games"] == [] and modo["level"] == 0


def test_staff_bot_down(client, fake_db, monkeypatch):
    _bot(monkeypatch, None)
    r = client.get("/staff")
    assert r.status_code == 200
    assert r.json() == {"staff": [], "stale": True}


def test_staff_bot_down_serves_last_list(client, fake_db, monkeypatch):
    _bot(monkeypatch, BOT_STAFF)
    assert len(client.get("/staff").json()["staff"]) == 2
    bot_client.clear_cache()
    _bot(monkeypatch, None)
    body = client.get("/staff").json()
    assert body["stale"] is True and len(body["staff"]) == 2
    assert "staff" not in bot_client._cache  # le dégradé n'est pas mis en cache


def test_staff_db_down_never_500(client, fake_db, monkeypatch):
    def boom(sql, *args):
        raise RuntimeError("base indisponible")

    _bot(monkeypatch, BOT_STAFF)
    fake_db.on("FROM", boom)
    r = client.get("/staff")
    assert r.status_code == 200
    body = r.json()
    assert body["stale"] is True
    assert body["staff"][0]["level"] is None and body["staff"][0]["motto"] is None
    assert "staff" not in bot_client._cache


def test_put_me_requires_login(client, fake_db):
    assert client.put("/staff/me", json={"motto": "x", "games": []}).status_code == 401


def test_put_me_forbidden_for_member(client, fake_db, monkeypatch, as_user):
    _bot(monkeypatch, BOT_STAFF)
    as_user("999")
    r = client.put("/staff/me", json={"motto": "x", "games": []})
    assert r.status_code == 403
    assert not [c for c in fake_db.calls if c[0] == "execute"]


def test_put_me_ok_for_staff(client, fake_db, monkeypatch, as_user):
    _bot(monkeypatch, BOT_STAFF)
    as_user("2")
    r = client.put("/staff/me", json={"motto": " Salut ", "games": ["lol", " minecraft "]})
    assert r.status_code == 200
    writes = [c for c in fake_db.calls if c[0] == "execute"]
    assert len(writes) == 1
    assert writes[0][2] == (2, "Salut", ["lol", "minecraft"])
    assert "staff" not in bot_client._cache  # cache invalidé


def test_put_me_rejects_long_motto(client, fake_db, monkeypatch, as_user):
    _bot(monkeypatch, BOT_STAFF)
    as_user("1")
    assert client.put("/staff/me", json={"motto": "a" * 141, "games": []}).status_code == 422
    assert client.put("/staff/me", json={"motto": "a" * 140, "games": []}).status_code == 200


@pytest.mark.parametrize("games", [["a"] * 6, [""], ["  "], [1], "Valorant"])
def test_put_me_rejects_bad_games(client, fake_db, monkeypatch, as_user, games):
    _bot(monkeypatch, BOT_STAFF)
    as_user("1")
    assert client.put("/staff/me", json={"motto": None, "games": games}).status_code == 422


def test_put_me_503_when_list_unknown(client, fake_db, monkeypatch, as_user):
    _bot(monkeypatch, None)
    as_user("1")
    r = client.put("/staff/me", json={"motto": "x", "games": []})
    assert r.status_code == 503
    assert not [c for c in fake_db.calls if c[0] == "execute"]


def test_put_me_uses_last_known_list(client, fake_db, monkeypatch, as_user):
    _bot(monkeypatch, BOT_STAFF)
    client.get("/staff")
    bot_client.clear_cache()
    _bot(monkeypatch, None)
    as_user("2")
    assert client.put("/staff/me", json={"motto": "x", "games": []}).status_code == 200
    as_user("999")
    assert client.put("/staff/me", json={"motto": "x", "games": []}).status_code == 403


def test_admin_put_requires_admin(client, fake_db, monkeypatch, as_user):
    _bot(monkeypatch, BOT_STAFF)
    as_user("2", is_admin=False)
    assert client.put("/admin/staff/2", json={"motto": "x", "games": []}).status_code == 403


def test_admin_put_ok(client, fake_db, monkeypatch, as_user):
    _bot(monkeypatch, BOT_STAFF)
    as_user("1", is_admin=True)
    r = client.put("/admin/staff/2", json={"motto": "Boss", "games": ["lol"]})
    assert r.status_code == 200
    writes = [c for c in fake_db.calls if c[0] == "execute"]
    assert writes[0][2] == (2, "Boss", ["lol"])


def test_admin_put_unknown_member_404(client, fake_db, monkeypatch, as_user):
    _bot(monkeypatch, BOT_STAFF)
    as_user("1", is_admin=True)
    assert client.put("/admin/staff/999", json={"motto": "x", "games": []}).status_code == 404
    assert not [c for c in fake_db.calls if c[0] == "execute"]


def test_admin_put_503_when_list_unknown(client, fake_db, monkeypatch, as_user):
    _bot(monkeypatch, None)
    as_user("1", is_admin=True)
    assert client.put("/admin/staff/2", json={"motto": "x", "games": []}).status_code == 503


@pytest.mark.parametrize("user_id", [0, -1, 10**20, 2**63])
def test_admin_put_rejects_out_of_range_id(client, fake_db, monkeypatch, as_user, user_id):
    _bot(monkeypatch, BOT_STAFF)
    as_user("1", is_admin=True)
    assert client.put(f"/admin/staff/{user_id}", json={"motto": "x", "games": []}).status_code == 422
    assert not [c for c in fake_db.calls if c[0] == "execute"]


def test_game_length_limit(client, fake_db, monkeypatch, as_user):
    _bot(monkeypatch, BOT_STAFF)
    as_user("1")
    assert client.put("/staff/me", json={"motto": None, "games": ["a" * 41]}).status_code == 422


def test_games_deduplicated(client, fake_db, monkeypatch, as_user):
    _bot(monkeypatch, BOT_STAFF)
    as_user("1")
    r = client.put("/staff/me", json={"motto": None, "games": ["lol", " LOL ", "minecraft"]})
    assert r.status_code == 200
    assert [c for c in fake_db.calls if c[0] == "execute"][0][2] == (1, None, ["lol", "minecraft"])


@pytest.mark.parametrize("bad", ["a" + chr(c) + "b" for c in (10, 9, 0, 0x2028, 0x7f)])
def test_control_chars_rejected(client, fake_db, monkeypatch, as_user, bad):
    _bot(monkeypatch, BOT_STAFF)
    as_user("1")
    assert client.put("/staff/me", json={"motto": bad, "games": []}).status_code == 422
    assert client.put("/staff/me", json={"motto": None, "games": [bad]}).status_code == 422
    assert not [c for c in fake_db.calls if c[0] == "execute"]


def test_staff_games_must_exist(client, fake_db, monkeypatch, as_user):
    _bot(monkeypatch, BOT_STAFF)
    as_user("1", is_admin=True)
    for url in ("/staff/me", "/admin/staff/2"):
        assert client.put(url, json={"motto": None, "games": ["lol", "valorant"]}).status_code == 422
        assert client.put(url, json={"motto": None, "games": ["lol", "dbd"]}).status_code == 200
    assert len([c for c in fake_db.calls if c[0] == "execute"]) == 2  # les refus n'écrivent rien
