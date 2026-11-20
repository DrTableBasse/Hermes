"""Tests des events programmés Discord : parse_xp_reward et GET /events."""
import pytest

import bot_client
import grades
from routes import events
from routes.events import parse_xp_reward


@pytest.fixture(autouse=True)
def _fresh_cache():
    bot_client.clear_cache()
    grades.clear_grades_cache()
    yield
    bot_client.clear_cache()
    grades.clear_grades_cache()


def _event(**over):
    base = {"id": 1111111111111111111, "name": "Soirée DBD", "description": "Soirée DBD\nXP: 200",
            "start": "2026-11-21T20:00:00+00:00", "end": None, "status": "scheduled",
            "location": "Vocal", "user_count": 4, "creator_id": 2222222222222222222,
            "image": None, "url": "https://discord.com/events/1/1111111111111111111"}
    return {**base, **over}


def _bot(monkeypatch, payload):
    async def fake_bot_get(path, timeout=1.5):
        assert path == "/events"
        return payload

    monkeypatch.setattr(events, "bot_get", fake_bot_get)


def test_parse_xp_basic():
    assert parse_xp_reward("Soirée DBD\nXP: 200") == 200


def test_parse_xp_case_spaces():
    assert parse_xp_reward("xp : 150") == 150


def test_parse_xp_absent():
    assert parse_xp_reward(None) is None
    assert parse_xp_reward("") is None
    assert parse_xp_reward("XP: abc") is None


def test_events_bot_down(client, fake_db, monkeypatch):
    _bot(monkeypatch, None)
    r = client.get("/events")
    assert r.status_code == 200
    assert r.json() == {"events": [], "stale": True}


def test_events_organizer_grade(client, fake_db, monkeypatch):
    _bot(monkeypatch, {"events": [
        _event(),
        _event(id=3, name="Avant", start="2026-11-21T18:00:00+00:00", description=None, creator_id=None),
    ]})
    fake_db.on("FROM user_voice_data", [
        {"user_id": 2222222222222222222, "username": "chef", "discord_avatar": "a.png",
         "current_level": 30},
    ])
    body = client.get("/events").json()
    assert [e["name"] for e in body["events"]] == ["Avant", "Soirée DBD"]  # trié par start
    avant, dbd = body["events"]
    assert avant["organizer"] is None and avant["xp_reward"] is None
    assert dbd["id"] == "1111111111111111111" and dbd["xp_reward"] == 200
    assert dbd["organizer"] == {
        "id": "2222222222222222222", "name": "chef", "avatar": "a.png",
        "grade": {"name": "Colonel Saucisson", "slug": "colonel", "color": "#3FE0F0"},
    }


def test_events_organizer_unknown_or_null_level(client, fake_db, monkeypatch):
    _bot(monkeypatch, {"events": [_event()]})
    fake_db.on("FROM user_voice_data", [
        {"user_id": 2222222222222222222, "username": "chef", "discord_avatar": None, "current_level": None},
    ])
    org = client.get("/events").json()["events"][0]["organizer"]
    assert org["grade"]["slug"] == "recrue" and org["avatar"] is None
