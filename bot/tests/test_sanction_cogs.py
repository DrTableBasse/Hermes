"""Cogs de sanction : la ligne de journal est écrite après la réponse, et seulement en cas de succès."""
import asyncio
import inspect
import os
import sys
from types import SimpleNamespace as N

import discord
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cogs.moderation import kick as kick_module  # noqa: E402


class FakeResponse:
    def __init__(self, events):
        self.events = events

    async def send_message(self, *args, **kwargs):
        self.events.append(("response", kwargs.get("ephemeral", False)))


def _forbidden():
    return discord.Forbidden(N(status=403, reason="Forbidden"), "missing permissions")


@pytest.fixture
def kick_env(monkeypatch):
    events = []

    async def fake_record(**kwargs):
        events.append(("record", kwargs))

    async def noop(*args, **kwargs):
        return None

    monkeypatch.setattr(kick_module, "record", fake_record)
    monkeypatch.setattr(kick_module, "send_sanction_dm", noop)
    monkeypatch.setattr(kick_module, "log_admin_action", noop)
    monkeypatch.setattr(kick_module, "moderation_embed", lambda *a, **k: "embed")
    interaction = N(
        user=N(id=7, display_name="Modo", top_role=10),
        guild=N(name="SaucisseLand", icon=None),
        response=FakeResponse(events),
    )
    cog = kick_module.KickCog(bot=None)
    # Corps de la commande sans les décorateurs (rôle admin, activation en base, log).
    callback = inspect.unwrap(kick_module.KickCog.kick.callback)
    return events, interaction, cog, callback


def _member(kick):
    return N(id=5, display_name="Bob", top_role=1, kick=kick)


def test_kick_success_records_after_response(kick_env):
    events, interaction, cog, callback = kick_env

    async def kick(reason):
        events.append(("kick", reason))

    asyncio.run(callback(cog, interaction, _member(kick), "spam"))
    assert [e[0] for e in events] == ["kick", "response", "record"]
    row = events[2][1]
    assert (row["kind"], row["action"], row["source"]) == ("sanction", "kick", "hermes")
    assert (row["actor_id"], row["target_id"], row["details"]) == (7, 5, {"reason": "spam"})


def test_kick_forbidden_records_nothing(kick_env):
    events, interaction, cog, callback = kick_env

    async def kick(reason):
        raise _forbidden()

    asyncio.run(callback(cog, interaction, _member(kick), "spam"))
    assert events == [("response", True)]
