"""Tests du statut d'Hermes : availability() et GET /hermes/status."""
from datetime import datetime, timedelta, timezone

import pytest

import bot_client
from routes import hermes
from routes.hermes import availability

NOW = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _fresh_cache(monkeypatch):
    monkeypatch.setattr(hermes, "_last_good", None)
    bot_client.clear_cache()
    yield
    bot_client.clear_cache()


def _bot(monkeypatch, payload):
    async def fake_bot_get(path, timeout=1.5):
        assert path == "/status"
        return payload

    monkeypatch.setattr(hermes, "bot_get", fake_bot_get)


def test_availability_before_30_days():
    since = NOW - timedelta(days=10)
    result = availability(14_000, since, NOW)
    assert result["percent"] is None
    assert result["since"] == since.isoformat()


def test_availability_after_30_days():
    since = NOW - timedelta(days=45)
    result = availability(43_200, since, NOW)
    assert result["percent"] == 100.0


def test_availability_partial_and_capped():
    since = NOW - timedelta(days=45)
    assert availability(21_600, since, NOW)["percent"] == 50.0
    assert availability(50_000, since, NOW)["percent"] == 100.0  # jamais > 100


def test_hermes_bot_down(client, fake_db, monkeypatch):
    _bot(monkeypatch, None)
    r = client.get("/hermes/status")
    assert r.status_code == 200
    body = r.json()
    assert body["online"] is False and body["latency_ms"] is None
    assert body["today"]["xp_distributed"] is None


def test_hermes_online(client, fake_db, monkeypatch):
    _bot(monkeypatch, {"ready": True, "latency_ms": 42, "started_at": NOW.isoformat(), "guilds": 1})
    fake_db.on("FROM bot_heartbeats", {"n": 100, "first": NOW - timedelta(days=3)})
    fake_db.on("FROM user_command_stats", 1234)
    fake_db.on("FROM user_achievements", 5)
    fake_db.on("FROM tickets", 2)
    fake_db.on("FROM bump_reminder_state", 1)
    body = client.get("/hermes/status").json()
    assert body["online"] is True and body["latency_ms"] == 42
    assert body["commands_served"] == 1234
    assert body["availability"]["percent"] is None
    assert body["today"] == {"xp_distributed": None, "achievements": 5, "tickets": 2, "bump_reminders": 1}
    assert isinstance(body["daily_curve"], list)


def test_hermes_not_ready_is_offline(client, fake_db, monkeypatch):
    _bot(monkeypatch, {"ready": False, "latency_ms": 0, "started_at": NOW.isoformat(), "guilds": 0})
    body = client.get("/hermes/status").json()
    assert body["online"] is False and body["latency_ms"] is None


def test_hermes_db_down_never_500(client, fake_db, monkeypatch):
    def boom(sql, *args):
        raise RuntimeError("base indisponible")

    _bot(monkeypatch, {"ready": True, "latency_ms": 30, "started_at": NOW.isoformat(), "guilds": 1})
    fake_db.on("FROM", boom)
    r = client.get("/hermes/status")
    assert r.status_code == 200
    body = r.json()
    assert body["online"] is True and body["commands_served"] is None
    assert body["availability"]["percent"] is None


def test_hermes_malformed_bot_payload(client, fake_db, monkeypatch):
    _bot(monkeypatch, {"ready": True, "latency_ms": "abc"})
    assert client.get("/hermes/status").status_code == 200
