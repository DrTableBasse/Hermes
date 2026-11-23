"""Branchements du journal : journal d'audit Discord, commandes, purge quotidienne."""
import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as N

import discord
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cogs.system import audit_journal  # noqa: E402
from utils import audit_events  # noqa: E402

BOT_ID = 42
MOD_ID = 7


class Spy:
    """Faux coroutine : mémorise les appels (kwargs) et renvoie une valeur fixe."""

    def __init__(self, result=None, error=None):
        self.calls = []
        self.result = result
        self.error = error

    async def __call__(self, *args, **kwargs):
        self.calls.append(kwargs or args)
        if self.error:
            raise self.error
        return self.result


def _entry(action, user_id, target=None, before=None, after=None, entry_id=999, reason="raison"):
    user = N(id=user_id, display_name=f"user{user_id}", name=f"user{user_id}")
    return N(
        action=action, user_id=user_id, user=user, id=entry_id, reason=reason,
        target=target if target is not None else N(id=5, display_name="Bob", name="bob"),
        before=before, after=after,
    )


@pytest.fixture
def journal(monkeypatch):
    record, attach = Spy(result=1), Spy(result=False)
    monkeypatch.setattr(audit_journal, "record", record)
    monkeypatch.setattr(audit_journal, "attach_discord_entry", attach)
    monkeypatch.setattr(audit_journal, "MERGE_RETRY_S", 0)
    cog = audit_journal.AuditJournal(N(user=N(id=BOT_ID)))
    return cog, record, attach


def test_should_merge_only_bot_entries():
    from cogs.system.audit_journal import should_merge
    assert should_merge(42, 42) is True
    assert should_merge(7, 42) is False
    assert should_merge(None, 42) is False


def test_bot_entry_without_match_falls_back_to_discord_row(journal):
    cog, record, attach = journal
    asyncio.run(cog.on_audit_log_entry_create(_entry(discord.AuditLogAction.kick, BOT_ID)))
    # une tentative puis une seconde après le délai (la ligne site arrive après l'évènement)
    assert attach.calls == [{"action": "kick", "target_id": 5, "audit_id": 999}] * 2
    assert len(record.calls) == 1
    row = record.calls[0]
    assert row["kind"] == "sanction" and row["action"] == "kick"
    assert row["source"] == "discord" and row["actor_id"] == BOT_ID
    assert row["target_id"] == 5 and row["target_name"] == "Bob"
    assert row["details"] == {"reason": "raison", "discord_audit_id": 999}


def test_bot_entry_with_match_is_not_recorded_twice(journal):
    cog, record, attach = journal
    attach.result = True
    asyncio.run(cog.on_audit_log_entry_create(_entry(discord.AuditLogAction.ban, BOT_ID)))
    assert attach.calls == [{"action": "ban", "target_id": 5, "audit_id": 999}]
    assert record.calls == []


def test_human_entry_recorded_as_discord_source(journal):
    cog, record, attach = journal
    asyncio.run(cog.on_audit_log_entry_create(_entry(discord.AuditLogAction.kick, MOD_ID)))
    assert attach.calls == []
    assert len(record.calls) == 1
    row = record.calls[0]
    assert (row["kind"], row["action"], row["source"]) == ("sanction", "kick", "discord")
    assert row["actor_id"] == MOD_ID and row["actor_name"] == f"user{MOD_ID}"


def test_member_update_timeout_recorded(journal):
    cog, record, _ = journal
    future = datetime.now(timezone.utc) + timedelta(minutes=10)
    entry = _entry(
        discord.AuditLogAction.member_update, MOD_ID,
        before=N(timed_out_until=None), after=N(timed_out_until=future),
    )
    asyncio.run(cog.on_audit_log_entry_create(entry))
    assert [(r["kind"], r["action"]) for r in record.calls] == [("sanction", "timeout")]


def test_member_update_nickname_recorded_as_member_event(journal):
    cog, record, attach = journal
    entry = _entry(
        discord.AuditLogAction.member_update, MOD_ID,
        before=N(nick="a"), after=N(nick="b"),
    )
    asyncio.run(cog.on_audit_log_entry_create(entry))
    assert attach.calls == []
    assert [(r["kind"], r["action"], r["source"]) for r in record.calls] == [("member", "nickname", "discord")]
    row = record.calls[0]
    assert (row["actor_id"], row["target_id"], row["target_name"]) == (MOD_ID, 5, "Bob")
    assert row["details"] == {
        "changes": {"nick": {"avant": "a", "après": "b"}},
        "reason": "raison", "discord_audit_id": 999,
    }


def test_member_update_timeout_and_nickname_gives_both_once(journal):
    cog, record, _ = journal
    future = datetime.now(timezone.utc) + timedelta(minutes=10)
    entry = _entry(
        discord.AuditLogAction.member_update, MOD_ID,
        before=N(timed_out_until=None, nick="a"), after=N(timed_out_until=future, nick="b"),
    )
    asyncio.run(cog.on_audit_log_entry_create(entry))
    assert [(r["kind"], r["action"]) for r in record.calls] == [("sanction", "timeout"), ("member", "nickname")]


def test_unmapped_action_is_ignored(journal):
    cog, record, attach = journal
    asyncio.run(cog.on_audit_log_entry_create(_entry(discord.AuditLogAction.webhook_create, MOD_ID)))
    assert record.calls == [] and attach.calls == []


class Diff:
    """Imite AuditLogDiff : itérable en paires (champ, valeur)."""

    def __init__(self, **fields):
        self.__dict__.update(fields)

    def __iter__(self):
        return iter(self.__dict__.items())


def test_role_create_recorded_with_changes(journal):
    cog, record, attach = journal
    entry = _entry(
        discord.AuditLogAction.role_create, MOD_ID, target=N(id=50, name="Modo"),
        before=Diff(), after=Diff(name="Modo", colour=discord.Colour(0xFF0000)),
    )
    asyncio.run(cog.on_audit_log_entry_create(entry))
    assert attach.calls == []
    row, = record.calls
    assert (row["kind"], row["action"], row["source"]) == ("role", "create", "discord")
    assert (row["target_id"], row["target_name"]) == (50, "Modo")
    assert row["details"]["changes"] == {
        "name": {"avant": None, "après": "Modo"}, "colour": {"avant": None, "après": "#FF0000"},
    }


def test_deleted_role_named_from_before_values(journal):
    cog, record, _ = journal
    entry = _entry(
        discord.AuditLogAction.role_delete, MOD_ID, target=discord.Object(id=50),
        before=Diff(name="Ancien"), after=Diff(),
    )
    asyncio.run(cog.on_audit_log_entry_create(entry))
    assert (record.calls[0]["target_id"], record.calls[0]["target_name"]) == (50, "Ancien")


def test_member_role_update_one_row_per_role(journal):
    cog, record, _ = journal
    entry = _entry(
        discord.AuditLogAction.member_role_update, BOT_ID,
        before=Diff(roles=[N(id=1, name="A")]), after=Diff(roles=[N(id=2, name="B")]),
    )
    asyncio.run(cog.on_audit_log_entry_create(entry))
    assert [(r["kind"], r["action"], r["details"]["role"]) for r in record.calls] == [
        ("member_role", "add", "B"), ("member_role", "remove", "A"),
    ]
    assert all(r["source"] == "discord" and r["target_id"] == 5 for r in record.calls)


def test_overwrite_names_the_role_or_member(journal):
    cog, record, _ = journal
    entry = _entry(
        discord.AuditLogAction.overwrite_update, MOD_ID, target=N(id=300, name="general"),
        before=Diff(deny=discord.Permissions.none()), after=Diff(deny=discord.Permissions(send_messages=True)),
    )
    entry.extra = N(id=60, name="Muet")
    asyncio.run(cog.on_audit_log_entry_create(entry))
    row, = record.calls
    assert (row["kind"], row["action"], row["target_name"]) == ("channel", "update", "general")
    assert row["details"]["permissions"] == {"deny": {"avant": [], "après": ["send_messages"]}}
    assert row["details"]["overwrite_for"] == "Muet"


def test_message_delete_by_moderator_completes_message_row(journal, monkeypatch):
    cog, record, _ = journal
    deleted_by = Spy(result=True)
    monkeypatch.setattr(audit_journal, "attach_deleted_by", deleted_by)
    entry = _entry(discord.AuditLogAction.message_delete, MOD_ID)
    entry.extra = N(channel=N(id=300, name="general"), count=1)
    asyncio.run(cog.on_audit_log_entry_create(entry))
    assert [(r["kind"], r["action"]) for r in record.calls] == [("sanction", "message_delete")]
    assert deleted_by.calls == [{
        "author_id": 5, "author_name": "Bob", "channel_id": 300,
        "moderator_id": MOD_ID, "moderator_name": f"user{MOD_ID}",
    }]


def test_message_delete_retries_once_when_row_not_yet_written(journal, monkeypatch):
    cog, _, _ = journal
    deleted_by = Spy(result=False)
    monkeypatch.setattr(audit_journal, "attach_deleted_by", deleted_by)
    monkeypatch.setattr(audit_journal, "DELETED_BY_RETRY_S", 0)
    entry = _entry(discord.AuditLogAction.message_delete, MOD_ID)
    entry.extra = N(channel=N(id=300, name="general"), count=1)
    asyncio.run(cog.on_audit_log_entry_create(entry))
    assert len(deleted_by.calls) == 2


def test_bot_bulk_delete_merges_with_hermes_clear(journal):
    cog, record, attach = journal
    attach.result = True
    entry = _entry(discord.AuditLogAction.message_bulk_delete, BOT_ID, target=N(id=300, name="general"))
    asyncio.run(cog.on_audit_log_entry_create(entry))
    assert attach.calls == [{"action": "clear", "target_id": None, "audit_id": 999}]
    assert record.calls == []


def test_target_without_name_keeps_id_only(journal):
    cog, record, _ = journal
    asyncio.run(cog.on_audit_log_entry_create(
        _entry(discord.AuditLogAction.unban, MOD_ID, target=discord.Object(id=77))
    ))
    row = record.calls[0]
    assert row["target_id"] == 77 and row["target_name"] is None


def test_missing_audit_permission_warns_once(monkeypatch, caplog):
    monkeypatch.setattr(audit_journal, "_permission_warned", False)
    guild = N(me=N(guild_permissions=N(view_audit_log=False)))
    with caplog.at_level(logging.WARNING, logger=audit_journal.logger.name):
        assert audit_journal.warn_if_audit_log_hidden(guild) is True
        assert audit_journal.warn_if_audit_log_hidden(guild) is True
    warnings = [r for r in caplog.records if "Voir les logs du serveur" in r.getMessage()]
    assert len(warnings) == 1
    assert "sanctions natives non journalisées" in warnings[0].getMessage()


def test_audit_permission_present_no_warning(monkeypatch, caplog):
    monkeypatch.setattr(audit_journal, "_permission_warned", False)
    guild = N(me=N(guild_permissions=N(view_audit_log=True)))
    with caplog.at_level(logging.WARNING, logger=audit_journal.logger.name):
        assert audit_journal.warn_if_audit_log_hidden(guild) is False
    assert caplog.records == []


def test_purge_once_logs_count(monkeypatch):
    purge = Spy(result=12)
    monkeypatch.setattr(audit_journal, "purge_older_than", purge)
    assert asyncio.run(audit_journal.purge_once()) == 12
    assert purge.calls == [(365,)]


def test_purge_once_swallows_errors(monkeypatch, caplog):
    monkeypatch.setattr(audit_journal, "purge_older_than", Spy(error=RuntimeError("db down")))
    with caplog.at_level(logging.WARNING, logger=audit_journal.logger.name):
        assert asyncio.run(audit_journal.purge_once()) is None
    assert any("db down" in r.getMessage() for r in caplog.records)


# ── Commandes ────────────────────────────────────────────────────────────────

def _interaction(channel, guild, namespace):
    ns = discord.app_commands.Namespace.__new__(discord.app_commands.Namespace)
    ns.__dict__.update(namespace)
    return N(user=N(id=MOD_ID, display_name="Modo"), channel=channel, guild=guild, namespace=ns)


def test_dm_command_has_no_channel(monkeypatch):
    record = Spy(result=1)
    monkeypatch.setattr(audit_events, "record", record)
    interaction = _interaction(channel=None, guild=None, namespace={"membre": "Bob"})
    command = N(name="voir", qualified_name="rang voir")
    asyncio.run(audit_events.record_command(interaction, command, success=True))
    assert record.calls == [{
        "kind": "command", "action": "/rang voir", "source": "hermes",
        "actor_id": MOD_ID, "actor_name": "Modo",
        "channel_id": None, "channel_name": None,
        "success": True, "details": {"options": {"membre": "Bob"}},
    }]


def test_dm_channel_without_guild_has_no_channel(monkeypatch):
    record = Spy(result=1)
    monkeypatch.setattr(audit_events, "record", record)
    dm = N(id=555, name=None)  # salon privé : présent mais hors serveur
    interaction = _interaction(channel=dm, guild=None, namespace={})
    asyncio.run(audit_events.record_command(interaction, N(qualified_name="ping"), success=True))
    assert record.calls[0]["channel_id"] is None


def test_guild_command_failure_masks_confess(monkeypatch):
    record = Spy(result=1)
    monkeypatch.setattr(audit_events, "record", record)
    interaction = _interaction(
        channel=N(id=300, name="general"), guild=N(id=1), namespace={"message": "secret"},
    )
    asyncio.run(audit_events.record_command(interaction, N(qualified_name="confess"), success=False))
    row = record.calls[0]
    assert (row["channel_id"], row["channel_name"]) == (300, "general")
    assert row["success"] is False
    assert row["details"] == {"options": {"message": "[masqué]"}}


def test_record_command_without_command_is_ignored(monkeypatch):
    record = Spy(result=1)
    monkeypatch.setattr(audit_events, "record", record)
    interaction = _interaction(channel=None, guild=None, namespace={})
    asyncio.run(audit_events.record_command(interaction, None, success=False))
    assert record.calls == []
