"""Journal des évènements du serveur : mise en forme pure et écouteurs."""
import asyncio
import os
import sys
from types import SimpleNamespace as V

import discord
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def vs(**kw):
    base = dict(channel=None, self_mute=False, self_deaf=False, mute=False, deaf=False, self_stream=False)
    return V(**{**base, **kw})


# ── Brief ────────────────────────────────────────────────────────────────────

def test_voice_move_is_single_action():
    from utils.server_events import voice_actions
    assert voice_actions(vs(channel=1), vs(channel=2)) == ["move"]


def test_voice_join_leave_and_mute():
    from utils.server_events import voice_actions
    assert voice_actions(vs(), vs(channel=1)) == ["join"]
    assert voice_actions(vs(channel=1), vs()) == ["leave"]
    assert voice_actions(vs(channel=1), vs(channel=1, self_mute=True)) == ["self_mute"]
    assert voice_actions(vs(channel=1), vs(channel=1, mute=True)) == ["server_mute"]


def test_message_snapshot_truncates_and_marks_unavailable():
    from utils.server_events import message_snapshot, MAX_CONTENT_LEN
    assert len(message_snapshot("x" * 5000, [], 0)["content"]) == MAX_CONTENT_LEN + 1
    assert message_snapshot(None, ["a.png"], 2) == {"content": "[contenu indisponible]", "attachments": ["a.png"], "embeds": 2}


def test_audit_member_role_update_splits_add_remove():
    from utils.server_events import audit_to_events
    ev = audit_to_events(discord.AuditLogAction.member_role_update, {"roles": [V(id=1, name="A")]}, {"roles": [V(id=2, name="B")]})
    assert [(k, a) for k, a, _ in ev] == [("member_role", "add"), ("member_role", "remove")]


def test_diff_details_only_changed_fields():
    from utils.server_events import diff_details
    assert diff_details({"name": "a", "hoist": False}, {"name": "b", "hoist": False}) == {"changes": {"name": {"avant": "a", "après": "b"}}}


# ── Mise en forme ────────────────────────────────────────────────────────────

def test_voice_unchanged_state_gives_nothing():
    from utils.server_events import voice_actions
    assert voice_actions(vs(channel=1), vs(channel=1)) == []


def test_voice_flags_both_directions_and_stream():
    from utils.server_events import voice_actions
    assert voice_actions(vs(channel=1, self_mute=True), vs(channel=1)) == ["self_mute"]
    assert voice_actions(vs(channel=1), vs(channel=1, deaf=True, self_deaf=True)) == ["server_deafen", "self_deafen"]
    assert voice_actions(vs(channel=1), vs(channel=1, self_stream=True)) == ["stream_start"]
    assert voice_actions(vs(channel=1, self_stream=True), vs(channel=1)) == ["stream_stop"]


def test_voice_leave_while_streaming_is_only_leave():
    from utils.server_events import voice_actions
    assert voice_actions(vs(channel=1, self_stream=True, self_mute=True), vs()) == ["leave"]


def test_message_snapshot_short_content_kept():
    from utils.server_events import message_snapshot
    assert message_snapshot("salut", [], 0) == {"content": "salut", "attachments": [], "embeds": 0}


def test_diff_details_readable_values():
    from utils.server_events import diff_details
    changes = diff_details(
        {"colour": discord.Colour(0x12AB34), "permissions": discord.Permissions(send_messages=True)},
        {"colour": discord.Colour(0xFF0000), "permissions": discord.Permissions(send_messages=True, kick_members=True)},
    )["changes"]
    assert changes["colour"] == {"avant": "#12AB34", "après": "#FF0000"}
    assert changes["permissions"] == {"avant": ["send_messages"], "après": ["kick_members", "send_messages"]}


def test_diff_details_enum_object_and_missing_side():
    from utils.server_events import diff_details
    changes = diff_details({}, {"type": discord.ChannelType.text, "category": V(id=3, name="Jeux")})["changes"]
    assert changes == {"type": {"avant": None, "après": "text"}, "category": {"avant": None, "après": "Jeux"}}


def test_audit_role_channel_thread_emoji_invite_server():
    from utils.server_events import audit_to_events
    A = discord.AuditLogAction
    cases = {
        A.role_create: ("role", "create"), A.role_update: ("role", "update"), A.role_delete: ("role", "delete"),
        A.channel_create: ("channel", "create"), A.channel_update: ("channel", "update"),
        A.channel_delete: ("channel", "delete"),
        A.thread_create: ("thread", "create"), A.thread_update: ("thread", "update"),
        A.thread_delete: ("thread", "delete"),
        A.emoji_create: ("emoji", "create"), A.emoji_update: ("emoji", "update"), A.emoji_delete: ("emoji", "delete"),
        A.sticker_create: ("emoji", "create"), A.sticker_update: ("emoji", "update"),
        A.sticker_delete: ("emoji", "delete"),
        A.invite_create: ("invite", "create"), A.invite_delete: ("invite", "delete"),
        A.guild_update: ("server", "update"),
    }
    for action, expected in cases.items():
        ev = audit_to_events(action, {"name": "a"}, {"name": "b"})
        assert [(k, a) for k, a, _ in ev] == [expected], action
        assert ev[0][2] == {"changes": {"name": {"avant": "a", "après": "b"}}}


def test_audit_overwrites_are_channel_permission_updates():
    from utils.server_events import audit_to_events
    for action in (discord.AuditLogAction.overwrite_create, discord.AuditLogAction.overwrite_update,
                   discord.AuditLogAction.overwrite_delete):
        ev = audit_to_events(action, {"deny": discord.Permissions.none()},
                             {"deny": discord.Permissions(send_messages=True)})
        assert ev == [("channel", "update", {"permissions": {"deny": {"avant": [], "après": ["send_messages"]}}})]


def test_audit_member_update_nickname_only():
    from utils.server_events import audit_to_events
    A = discord.AuditLogAction
    assert audit_to_events(A.member_update, {"nick": "a"}, {"nick": "b"}) == [
        ("member", "nickname", {"changes": {"nick": {"avant": "a", "après": "b"}}})
    ]
    # timeout seul : c'est une sanction, traitée ailleurs
    assert audit_to_events(A.member_update, {"timed_out_until": None}, {"timed_out_until": 1}) == []


def test_audit_member_role_details():
    from utils.server_events import audit_to_events
    ev = audit_to_events(discord.AuditLogAction.member_role_update, {}, {"roles": [V(id=2, name="B")]})
    assert ev == [("member_role", "add", {"role": "B", "role_id": 2})]


def test_audit_untracked_and_sanctions_give_nothing():
    from utils.server_events import audit_to_events
    A = discord.AuditLogAction
    for action in (A.webhook_create, A.kick, A.ban, A.unban, A.message_delete, A.message_bulk_delete):
        assert audit_to_events(action, {"name": "a"}, {"name": "b"}) == []


# ── Écouteurs (server_journal) ───────────────────────────────────────────────

class Spy:
    def __init__(self, result=None):
        self.calls = []
        self.result = result

    async def __call__(self, *args, **kwargs):
        self.calls.append(kwargs or args)
        return self.result


@pytest.fixture
def journal(monkeypatch):
    from cogs.system import server_journal
    record = Spy(result=1)
    monkeypatch.setattr(server_journal, "record", record)
    channels = {300: V(id=300, name="general"), 301: V(id=301, name="vocal")}
    bot = V(get_channel=channels.get)
    return server_journal.ServerJournal(bot), record


def _author(bot=False):
    return V(id=5, bot=bot, display_name="Bob", name="bob")


def _message(content="hello", bot=False, attachments=(), embeds=0):
    return V(
        id=900, content=content, author=_author(bot),
        attachments=[V(filename=f) for f in attachments], embeds=[object()] * embeds,
    )


def test_edit_records_before_and_after(journal):
    cog, record = journal
    payload = V(
        guild_id=1, channel_id=300, message_id=900, cached_message=_message("avant", attachments=["a.png"]),
        data={"content": "après", "author": {"id": "5", "username": "bob"}, "attachments": [{"filename": "b.png"}],
              "embeds": [{}], "edited_timestamp": "x"},
    )
    asyncio.run(cog.on_raw_message_edit(payload))
    assert len(record.calls) == 1
    row = record.calls[0]
    assert (row["kind"], row["action"], row["source"]) == ("message", "edit", "discord")
    assert (row["actor_id"], row["channel_id"], row["channel_name"]) == (5, 300, "general")
    assert row["details"] == {
        "message_id": 900,
        "avant": {"content": "avant", "attachments": ["a.png"], "embeds": 0},
        "après": {"content": "après", "attachments": ["b.png"], "embeds": 1},
    }


def test_edit_without_text_change_or_from_bot_is_ignored(journal):
    cog, record = journal
    same = V(guild_id=1, channel_id=300, message_id=900, cached_message=_message("pareil"),
             data={"content": "pareil", "author": {"id": "5"}, "embeds": [{}]})
    uncached_unfurl = V(guild_id=1, channel_id=300, message_id=900, cached_message=None,
                        data={"content": "x", "author": {"id": "5"}, "edited_timestamp": None})
    from_bot = V(guild_id=1, channel_id=300, message_id=900, cached_message=None,
                 data={"content": "x", "author": {"id": "5", "bot": True}, "edited_timestamp": "x"})
    for payload in (same, uncached_unfurl, from_bot):
        asyncio.run(cog.on_raw_message_edit(payload))
    assert record.calls == []


def test_edit_uncached_marks_before_unavailable(journal):
    cog, record = journal
    payload = V(guild_id=1, channel_id=300, message_id=900, cached_message=None,
                data={"content": "neuf", "author": {"id": "5", "username": "bob", "global_name": "Bob"},
                      "edited_timestamp": "x"})
    asyncio.run(cog.on_raw_message_edit(payload))
    row = record.calls[0]
    assert row["actor_name"] == "Bob"
    assert row["details"]["avant"] == {"content": "[contenu indisponible]", "attachments": [], "embeds": 0}


def test_delete_cached_records_attachment_names(journal):
    cog, record = journal
    payload = V(guild_id=1, channel_id=300, message_id=900,
                cached_message=_message("bye", attachments=["photo.jpg"], embeds=2))
    asyncio.run(cog.on_raw_message_delete(payload))
    row = record.calls[0]
    assert (row["kind"], row["action"], row["actor_id"], row["actor_name"]) == ("message", "delete", 5, "Bob")
    assert row["details"] == {"message_id": 900, "content": "bye", "attachments": ["photo.jpg"], "embeds": 2}


def test_delete_uncached_and_bot_messages(journal):
    cog, record = journal
    asyncio.run(cog.on_raw_message_delete(V(guild_id=1, channel_id=300, message_id=901, cached_message=None)))
    asyncio.run(cog.on_raw_message_delete(
        V(guild_id=1, channel_id=300, message_id=902, cached_message=_message(bot=True))))
    asyncio.run(cog.on_raw_message_delete(V(guild_id=None, channel_id=300, message_id=903, cached_message=None)))
    assert len(record.calls) == 1
    row = record.calls[0]
    assert row["actor_id"] is None
    assert row["details"]["content"] == "[contenu indisponible]"


def test_bulk_delete_keeps_human_cached_messages(journal):
    cog, record = journal
    payload = V(guild_id=1, channel_id=300, message_ids={1, 2, 3},
                cached_messages=[_message("a"), _message("b", bot=True)])
    asyncio.run(cog.on_raw_bulk_message_delete(payload))
    row = record.calls[0]
    assert (row["kind"], row["action"], row["channel_id"]) == ("message", "bulk_delete", 300)
    assert row["details"]["count"] == 3
    assert row["details"]["messages"] == [
        {"author_id": 5, "author_name": "Bob", "content": "a", "attachments": [], "embeds": 0}
    ]


def test_voice_move_records_arrival_and_origin(journal):
    cog, record = journal
    member = V(id=5, display_name="Bob", bot=False)
    asyncio.run(cog.on_voice_state_update(member, vs(channel=V(id=300, name="general")),
                                          vs(channel=V(id=301, name="vocal"))))
    row = record.calls[0]
    assert (row["kind"], row["action"], row["channel_id"], row["channel_name"]) == ("voice", "move", 301, "vocal")
    assert row["details"] == {"from_channel": "general", "from_channel_id": 300}


def test_voice_leave_uses_departure_channel_and_mute_state(journal):
    cog, record = journal
    member = V(id=5, display_name="Bob", bot=False)
    room = V(id=301, name="vocal")
    asyncio.run(cog.on_voice_state_update(member, vs(channel=room), vs()))
    asyncio.run(cog.on_voice_state_update(member, vs(channel=room), vs(channel=room, mute=True)))
    leave, mute = record.calls
    assert (leave["action"], leave["channel_id"]) == ("leave", 301)
    assert (mute["action"], mute["details"]) == ("server_mute", {"active": True})
    # mise en sourdine par le serveur : l'auteur est un modérateur inconnu ici
    assert mute["actor_id"] is None and mute["target_id"] == 5


def test_member_join_with_invite_and_leave(journal):
    cog, record = journal
    member = V(id=5, display_name="Bob", bot=False)
    invite = V(code="abc", inviter=V(id=9, display_name="Alice", name="alice"))
    asyncio.run(cog.on_member_join_tracked(member, invite))
    asyncio.run(cog.on_member_join_tracked(member, None))
    asyncio.run(cog.on_member_remove(member))
    join, join_unknown, leave = record.calls
    assert (join["kind"], join["action"], join["actor_id"]) == ("member", "join", 5)
    assert join["details"] == {"invite_code": "abc", "inviter_id": 9, "inviter_name": "Alice"}
    assert join_unknown["details"] == {"invite_code": None}
    assert (leave["kind"], leave["action"]) == ("member", "leave")
