"""`GET /users/{id}/stats` : le membre lui-même, ou un détenteur de `moderation.view` (admin compris)."""
import pytest

from middleware import auth_middleware


@pytest.fixture(autouse=True)
def _fresh():
    from limiter import limiter
    limiter.reset()


@pytest.fixture
def as_user(client, monkeypatch):
    def _as(discord_id, is_admin=False, permissions=frozenset()):
        async def fake_session(token):
            return {"sub": discord_id, "is_admin": is_admin, "is_redacteur": False,
                    "permissions": frozenset(permissions)}

        monkeypatch.setattr(auth_middleware, "_fetch_session", fake_session)
        client.cookies.set("better-auth.session_token", "tok")
    return _as


def _program(fake_db):
    fake_db.on("FROM user_voice_data WHERE user_id", {
        "user_id": 42, "username": "cible", "nickname": None, "discord_avatar": None,
        "last_seen": None, "total_time": 3600,
    })
    fake_db.on("FROM warn WHERE user_id", 3)
    fake_db.on("FROM achievements", [{
        "id": 1, "condition_type": "messages", "condition_value": 0, "name": "n",
        "description": "d", "icon": "i", "points": 1, "unlocked_at": None,
    }])


def _achievement_writes(fake_db):
    return [c for c in fake_db.calls if c[0] == "execute" and "user_achievements" in c[1]]


def test_autre_membre_refuse_sans_ecriture(client, fake_db, as_user):
    _program(fake_db)
    as_user("7")
    r = client.get("/users/42/stats")
    assert r.status_code == 403
    assert "warn_count" not in r.text
    assert _achievement_writes(fake_db) == []


def test_membre_lui_meme_voit_sa_fiche_et_ses_succes(client, fake_db, as_user):
    _program(fake_db)
    as_user("42")
    r = client.get("/users/42/stats")
    assert r.status_code == 200
    assert r.json()["stats"]["warn_count"] == 3
    assert "last_seen" in r.json()["user"]
    assert len(_achievement_writes(fake_db)) == 1


def test_admin_lit_la_fiche_sans_ecrire_de_succes_pour_autrui(client, fake_db, as_user):
    _program(fake_db)
    as_user("7", is_admin=True)
    r = client.get("/users/42/stats")
    assert r.status_code == 200
    assert r.json()["stats"]["warn_count"] == 3
    assert _achievement_writes(fake_db) == []


def test_moderateur_lit_la_fiche_sans_ecrire_de_succes_pour_autrui(client, fake_db, as_user):
    _program(fake_db)
    as_user("7", permissions={"moderation.view"})
    r = client.get("/users/42/stats")
    assert r.status_code == 200
    assert r.json()["stats"]["warn_count"] == 3
    assert _achievement_writes(fake_db) == []


def test_autre_droit_que_moderation_view_refuse(client, fake_db, as_user):
    _program(fake_db)
    as_user("7", permissions={"tickets.manage", "moderation.act"})
    r = client.get("/users/42/stats")
    assert r.status_code == 403
    assert r.json()["detail"] == "Droit requis : Voir la modération et le journal"


def test_non_connecte_refuse(client, fake_db):
    assert client.get("/users/42/stats").status_code == 401
