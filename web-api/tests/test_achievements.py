"""Tests du catalogue public des succès : GET /achievements."""
import pytest

import bot_client

ROWS = [
    {"id": 4, "name": "Légende du chat", "description": "Envoyer 10 000 messages", "icon": "👑",
     "points": 100, "condition_type": "messages", "unlocked_count": 1},
    {"id": 1, "name": "Premier message", "description": "Envoyer votre premier message", "icon": "✉️",
     "points": 10, "condition_type": "messages", "unlocked_count": 120},
]


@pytest.fixture(autouse=True)
def _fresh():
    from limiter import limiter
    limiter.reset()
    bot_client.clear_cache()
    yield
    bot_client.clear_cache()


def test_catalogue_avec_compteurs_et_membres_actifs(client, fake_db):
    fake_db.on("FROM achievements", ROWS)
    fake_db.on("FROM user_voice_data WHERE is_member", 140)
    res = client.get("/achievements")
    assert res.status_code == 200
    body = res.json()
    assert body["members_total"] == 140
    assert [a["id"] for a in body["achievements"]] == [4, 1]
    assert body["achievements"][1] == {
        "id": 1, "name": "Premier message", "description": "Envoyer votre premier message", "icon": "✉️",
        "points": 10, "condition_type": "messages", "unlocked_count": 120,
    }
    assert "stale" not in body
    # Seuls les membres encore présents comptent, au numérateur comme au dénominateur.
    sql = next(c[1] for c in fake_db.calls if "from achievements" in c[1].lower())
    assert "is_member" in sql


def test_reponse_mise_en_cache_cinq_minutes(client, fake_db):
    fake_db.on("FROM achievements", ROWS)
    fake_db.on("FROM user_voice_data WHERE is_member", 140)
    client.get("/achievements")
    calls = len(fake_db.calls)
    assert client.get("/achievements").status_code == 200
    assert len(fake_db.calls) == calls


def test_base_illisible_jamais_de_500(client, fake_db):
    def boom(sql, *args):
        raise RuntimeError("pool fermé")

    fake_db.on("FROM achievements", boom)
    res = client.get("/achievements")
    assert res.status_code == 200
    assert res.json() == {"achievements": [], "members_total": 0, "stale": True}
    # L'échec n'est pas mémorisé : la base revenue, la requête suivante répond.
    fake_db.rules.clear()
    fake_db.on("FROM achievements", ROWS)
    fake_db.on("FROM user_voice_data WHERE is_member", 140)
    assert client.get("/achievements").json()["members_total"] == 140


def test_compteurs_nuls_et_valeurs_absentes(client, fake_db):
    fake_db.on("FROM achievements", [{**ROWS[0], "unlocked_count": None, "points": None}])
    fake_db.on("FROM user_voice_data WHERE is_member", None)
    body = client.get("/achievements").json()
    assert body["members_total"] == 0
    assert body["achievements"][0]["unlocked_count"] == 0
    assert body["achievements"][0]["points"] == 0
