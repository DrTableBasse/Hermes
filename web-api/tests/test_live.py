"""Tests de la caserne en direct : /live et /live/feed."""
from datetime import datetime, timedelta, timezone

import pytest

import bot_client
from routes import live

BOT_LIVE = {"members": 120, "online": 40, "in_voice": 7, "voice_avatars": ["a.png", "b.png"],
            "game_players": {"lol": 12, "dbd": 3}}


def _snapshot(**over):
    row = {"taken_at": datetime.now(timezone.utc) - timedelta(minutes=2),
           "members": 118, "online": 35, "in_voice": 5}
    return {**row, **over}


@pytest.fixture(autouse=True)
def _fresh_cache():
    bot_client.clear_cache()
    yield
    bot_client.clear_cache()


def _bot(monkeypatch, payload):
    async def fake_bot_get(path, timeout=1.5):
        assert path == "/live"
        return payload

    monkeypatch.setattr(live, "bot_get", fake_bot_get)


def test_live_ok(client, fake_db, monkeypatch):
    _bot(monkeypatch, BOT_LIVE)
    now_hour = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    fake_db.on("FROM guild_stats_snapshots ORDER BY taken_at DESC", _snapshot())
    fake_db.on("SUM(messages)", 321)
    fake_db.on("date_trunc('hour'", [{"hour": now_hour, "online": 30.4}])
    r = client.get("/live")
    body = r.json()
    assert r.status_code == 200
    assert body["stale"] is False
    assert (body["members"], body["online"], body["in_voice"]) == (120, 40, 7)
    assert body["voice_avatars"] == ["a.png", "b.png"] and body["game_players"] == {"lol": 12, "dbd": 3}
    assert body["messages_today"] == 321
    assert len(body["curve_24h"]) == 24
    assert body["curve_24h"][-1] == {"hour": now_hour.isoformat(), "online": 30}
    assert body["curve_24h"][0]["online"] == 0
    datetime.fromisoformat(body["updated_at"])


def test_live_bot_down(client, fake_db, monkeypatch):
    _bot(monkeypatch, None)
    taken = datetime.now(timezone.utc) - timedelta(minutes=3)
    fake_db.on("FROM guild_stats_snapshots ORDER BY taken_at DESC", _snapshot(taken_at=taken))
    r = client.get("/live")
    body = r.json()
    assert r.status_code == 200 and body["stale"] is True
    assert (body["members"], body["online"], body["in_voice"]) == (118, 35, 5)
    assert body["voice_avatars"] == [] and body["game_players"] == {}
    assert body["messages_today"] == 0 and len(body["curve_24h"]) == 24
    assert body["updated_at"] == taken.isoformat()


def test_live_no_data(client, fake_db, monkeypatch):
    _bot(monkeypatch, None)
    r = client.get("/live")
    assert r.status_code == 204 and r.content == b""


def test_live_is_cached(client, fake_db, monkeypatch):
    calls = []

    async def counting(path, timeout=1.5):
        calls.append(path)
        return BOT_LIVE

    monkeypatch.setattr(live, "bot_get", counting)
    fake_db.on("FROM guild_stats_snapshots ORDER BY taken_at DESC", _snapshot())
    client.get("/live")
    client.get("/live")
    assert len(calls) == 1
    bot_client.clear_cache()
    client.get("/live")
    assert len(calls) == 2


def test_messages_today_since_paris_midnight(client, fake_db, monkeypatch):
    _bot(monkeypatch, BOT_LIVE)
    fake_db.on("FROM guild_stats_snapshots ORDER BY taken_at DESC", _snapshot())
    client.get("/live")
    sums = [c for c in fake_db.calls if "sum(messages)" in c[1].lower()]
    start = sums[0][2][0]
    assert start.utcoffset() is not None
    paris = start.astimezone(live.PARIS)
    assert (paris.hour, paris.minute, paris.second) == (0, 0, 0)
    assert timedelta(0) <= datetime.now(timezone.utc) - start < timedelta(days=1, hours=1)


def test_feed_ids_are_strings(client, fake_db):
    big = 1234567890123456789
    at = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)
    fake_db.on("FROM user_notifications", [
        {"type": "level_up", "user_id": big, "username": "a", "avatar": None,
         "label": "Niveau 9 atteint !", "at": at},
        {"type": "achievement", "user_id": 42, "username": "b", "avatar": "x.png",
         "label": "💬 Bavard", "at": at},
    ])
    r = client.get("/live/feed")
    items = r.json()["items"]
    assert r.status_code == 200 and len(items) == 2
    assert [i["user_id"] for i in items] == [str(big), "42"]
    assert items[0]["avatar"] is None and items[0]["at"] == at.isoformat()
    assert items[1]["type"] == "achievement" and items[1]["label"] == "💬 Bavard"


def test_feed_empty(client, fake_db):
    assert client.get("/live/feed").json() == {"items": []}
