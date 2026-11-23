"""Module de journal : helpers purs, et SQL/arguments capturés via un faux db_manager."""
import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as N

import discord

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import audit_events  # noqa: E402
from utils.audit_events import (  # noqa: E402
    MAX_VALUE_LEN, command_options, map_audit_action, timeout_change,
)


class FakeDb:
    def __init__(self, result=None, error=None):
        self.calls = []
        self.result = result
        self.error = error

    async def fetchval(self, query, *args):
        self.calls.append((query, args))
        if self.error:
            raise self.error
        return self.result


class FakeAttachment(discord.Attachment):
    def __init__(self, filename):
        self.filename = filename


def test_command_options_truncates_and_masks():
    long = "x" * 900
    out = command_options("blague", {"texte": long})["texte"]
    assert len(out) == MAX_VALUE_LEN + 1 and out.endswith("…")
    assert command_options("confess", {"message": "secret"}) == {"message": "[masqué]"}


def test_command_options_attachment_by_filename_and_scalars():
    out = command_options("x", {"f": FakeAttachment("photo.png"), "n": 7, "o": True})
    assert out == {"f": "photo.png", "n": "7", "o": "True"}


def test_command_options_role_shown_with_name_and_id():
    role = discord.Role.__new__(discord.Role)
    role.name, role.id = "Modo", 42
    role._state = None
    assert command_options("x", {"r": role}) == {"r": "Modo (42)"}


def test_map_audit_action():
    assert map_audit_action(discord.AuditLogAction.kick) == ("sanction", "kick")
    assert map_audit_action(discord.AuditLogAction.ban) == ("sanction", "ban")
    assert map_audit_action(discord.AuditLogAction.unban) == ("sanction", "unban")
    assert map_audit_action(discord.AuditLogAction.message_delete) == (
        "sanction", "message_delete")
    assert map_audit_action(discord.AuditLogAction.message_bulk_delete) == (
        "sanction", "message_bulk_delete")
    assert map_audit_action(discord.AuditLogAction.channel_create) is None


def test_timeout_change():
    fut = datetime.now(timezone.utc) + timedelta(minutes=10)
    assert timeout_change(N(timed_out_until=None), N(timed_out_until=fut)) == "timeout"
    assert timeout_change(N(timed_out_until=fut), N(timed_out_until=None)) == "untimeout"
    assert timeout_change(N(timed_out_until=None), N(timed_out_until=None)) is None


def test_record_never_raises(monkeypatch, caplog):
    monkeypatch.setattr(audit_events, "db_manager", FakeDb(error=RuntimeError("panne")))
    with caplog.at_level(logging.WARNING):
        result = asyncio.run(audit_events.record(
            kind="command", action="/ping", source="hermes", actor_id=1, actor_name="a"))
    assert result is None
    assert any("Écriture du journal impossible" in r.getMessage() for r in caplog.records)


def test_record_inserts_row_and_returns_id(monkeypatch):
    db = FakeDb(result=17)
    monkeypatch.setattr(audit_events, "db_manager", db)
    result = asyncio.run(audit_events.record(
        kind="sanction", action="kick", source="hermes", actor_id=1, actor_name="a",
        target_id=2, details={"raison": "é"}))
    assert result == 17
    query, args = db.calls[0]
    assert "INSERT INTO audit_events" in query and "RETURNING id" in query
    assert args[:5] == ("sanction", "kick", "hermes", 1, "a")
    assert args[5] == 2 and args[9] is True
    assert args[10] == '{"raison": "é"}'


def test_attach_discord_entry_targets_recent_site_or_hermes_row(monkeypatch):
    db = FakeDb(result=5)
    monkeypatch.setattr(audit_events, "db_manager", db)
    ok = asyncio.run(audit_events.attach_discord_entry(
        action="kick", target_id=2, audit_id=999))
    assert ok is True
    query, args = db.calls[0]
    assert "source IN ('site','hermes')" in query
    assert "NOT details ? 'discord_audit_id'" in query
    assert "make_interval(secs => $4)" in query
    assert args == (999, "kick", 2, 120)


def test_attach_discord_entry_false_without_match(monkeypatch):
    monkeypatch.setattr(audit_events, "db_manager", FakeDb(result=None))
    assert asyncio.run(audit_events.attach_discord_entry(
        action="ban", target_id=3, audit_id=1)) is False


def test_purge_uses_365_days(monkeypatch):
    db = FakeDb(result=12)
    monkeypatch.setattr(audit_events, "db_manager", db)
    assert asyncio.run(audit_events.purge_older_than()) == 12
    query, args = db.calls[0]
    assert "DELETE FROM audit_events" in query
    assert "make_interval(days => $1)" in query
    assert args == (365,)
