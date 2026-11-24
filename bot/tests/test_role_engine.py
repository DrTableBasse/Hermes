"""Moteur de règles de rôles branché dans le bot : évènements, aperçu, rôles introuvables."""
import asyncio
import inspect
import logging
import os
import sys
from types import SimpleNamespace as N

import discord
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cogs.system import role_engine as engine_module  # noqa: E402
from cogs.system import achievements_notifier as notifier_module  # noqa: E402
from cogs.gamification import xp as xp_module  # noqa: E402
from cogs.moderation import voice as voice_module  # noqa: E402


# ── Faux Discord ─────────────────────────────────────────────────────────────

class FakeRole:
    def __init__(self, id, name, assignable=True, managed=False):
        self.id, self.name, self._assignable, self.managed = id, name, assignable, managed

    def is_assignable(self):
        return self._assignable


class FakeMember:
    def __init__(self, id, guild, roles=(), bot=False):
        self.id, self.guild, self.bot = id, guild, bot
        self.roles = list(roles)
        self.display_name = f"membre{id}"
        self.name = self.display_name
        self.calls = []

    async def add_roles(self, role, reason=None):
        self.calls.append(("add", role.id))
        self.roles.append(role)

    async def remove_roles(self, role, reason=None):
        self.calls.append(("remove", role.id))
        self.roles.remove(role)


class FakeGuild:
    def __init__(self, roles=()):
        self.roles = list(roles)
        self.members = []
        self.created = []

    def get_role(self, role_id):
        return next((r for r in self.roles if r.id == role_id), None)

    def get_member(self, user_id):
        return next((m for m in self.members if m.id == user_id), None)

    async def create_role(self, name, color, reason=None):
        role = FakeRole(9000 + len(self.created), name)
        self.created.append((name, color.value))
        self.roles.append(role)
        return role

    def member(self, id, roles=()):
        m = FakeMember(id, self, roles)
        self.members.append(m)
        return m


class FakeBot:
    def __init__(self, guild):
        self.guild = guild
        self.cogs = {}
        self.user = N(id=1, name="Hermes")

    def get_guild(self, _):
        return self.guild

    def get_cog(self, name):
        return self.cogs.get(name)

    async def wait_until_ready(self):
        await asyncio.Event().wait()


def rule_row(id, ctype, value, role_id=None, **kw):
    return {
        "id": id, "condition_type": ctype, "condition_value": str(value), "role_id": role_id,
        "remove_when_lost": kw.get("remove_when_lost", False), "exclusive_group": None,
        "active": True, "reconcile": False,
        "create_role_name": kw.get("create_role_name"), "create_role_color": kw.get("create_role_color"),
    }


class FakeDB:
    def __init__(self, rules, stats=None):
        self.rules = rules
        self.stats = stats or {}
        self.stats_calls = []
        self.executed = []

    async def fetch(self, sql, *args):
        if "FROM role_rules" in sql:
            return [dict(r) for r in self.rules]
        if "unnest" in sql:
            self.stats_calls.append(list(args[0]))
            base = dict(voice_seconds=0, messages=0, level=0, streak_days=0,
                        bumps=0, invites=0, achievements=[])
            return [{**base, **self.stats.get(uid, {}), "user_id": uid} for uid in args[0]]
        raise AssertionError(sql)

    async def execute(self, sql, *args):
        self.executed.append((sql, args))
        if "UPDATE role_rules SET role_id" in sql:
            role_id, rule_id = args
            for r in self.rules:
                if r["id"] == rule_id and r["role_id"] is None:
                    r["role_id"] = role_id
                    if "create_role_name = NULL" in sql:
                        r["create_role_name"] = r["create_role_color"] = None


@pytest.fixture
def env(monkeypatch):
    records = []

    async def fake_record(**kw):
        records.append(kw)

    async def fake_grades(_db):
        return [{"slug": "recrue", "level_min": 1, "name": "R", "color": "#000"}]

    monkeypatch.setattr(engine_module, "record", fake_record)
    monkeypatch.setattr(engine_module, "load_grades", fake_grades)

    def make(rules, stats=None, roles=()):
        db = FakeDB(rules, stats)
        monkeypatch.setattr(engine_module, "db_manager", db)
        guild = FakeGuild(roles)
        bot = FakeBot(guild)
        engine = engine_module.RoleEngine(bot)
        bot.cogs["RoleEngine"] = engine
        return N(db=db, guild=guild, bot=bot, engine=engine, records=records)

    return make


def run(coro_factory):
    """Exécute dans une boucle (les tâches du cog y démarrent) puis annule les tâches."""
    async def main():
        try:
            return await coro_factory()
        finally:
            for t in asyncio.all_tasks() - {asyncio.current_task()}:
                t.cancel()
    return asyncio.run(main())


class Stub:
    """Gestionnaire factice : toute méthode est une coroutine renvoyant la valeur prévue."""
    def __init__(self, **returns):
        self._returns = returns

    def __getattr__(self, name):
        async def method(*args, **kwargs):
            return self._returns.get(name)
        return method


# ── Évènements ───────────────────────────────────────────────────────────────

def test_voice_session_end_adds_batman_once(env, monkeypatch):
    batman = FakeRole(50, "Batman")
    monkeypatch.setattr(voice_module, "voice_manager", Stub(get_user={"total_time": 100 * 3600}))
    monkeypatch.setattr(voice_module, "db_manager", Stub(fetchval=1))
    monkeypatch.setattr(voice_module, "streak_manager", Stub(get_streak=None))
    monkeypatch.setattr(voice_module, "quest_manager", Stub(update_progress=[]))
    monkeypatch.setattr(voice_module, "achievement_manager", Stub(check_and_unlock=[]))

    async def scenario():
        e = env([rule_row(1, "voice_hours", 100, role_id=50)],
                stats={7: {"voice_seconds": 100 * 3600}}, roles=[batman])
        member = e.guild.member(7)
        voice = voice_module.VoiceCog(e.bot)
        await voice._update_time(member, 0)
        await voice._update_time(member, 0)
        return e, member

    e, member = run(scenario)
    assert member.calls == [("add", 50)]
    assert [(r["kind"], r["action"], r["source"], r["details"]["rule_id"]) for r in e.records] == [
        ("member_role", "add", "hermes", 1)]


def test_voice_below_threshold_adds_nothing(env):
    async def scenario():
        e = env([rule_row(1, "voice_hours", 100, role_id=50)],
                stats={7: {"voice_seconds": 99 * 3600}}, roles=[FakeRole(50, "Batman")])
        member = e.guild.member(7)
        return await e.engine.evaluate_member(member), member

    result, member = run(scenario)
    assert result == ([], [])
    assert member.calls == []


def test_level_up_to_rule_level_adds_role(env, monkeypatch):
    monkeypatch.setattr(xp_module, "streak_manager", Stub(get_streak=None))
    monkeypatch.setattr(xp_module, "xp_manager", Stub(add_xp={"leveled_up": True, "new_level": 10, "new_xp": 999}))
    monkeypatch.setattr(xp_module, "notification_manager", Stub())
    monkeypatch.setattr(xp_module, "achievement_manager", Stub(check_and_unlock=[]))

    async def scenario():
        e = env([rule_row(1, "level", 5, role_id=60), rule_row(2, "level", 20, role_id=61)],
                stats={7: {"level": 10}}, roles=[FakeRole(60, "Niv 5"), FakeRole(61, "Niv 20")])
        member = e.guild.member(7)
        await xp_module.XPCog(e.bot).award_xp(7, 10)
        return member

    member = run(scenario)
    assert member.calls == [("add", 60)]


def _notifier_env(env, monkeypatch, roles=()):
    created = []

    async def fake_notification(*args):
        created.append(args)

    async def fake_fetchrow(sql, *args):
        return {"id": 3, "name": "Pipelette", "icon": "💬", "description": "d", "points": 30}

    monkeypatch.setattr(notifier_module, "db_manager", N(fetchrow=fake_fetchrow))
    monkeypatch.setattr(notifier_module, "notification_manager", N(create=fake_notification))
    e = env([rule_row(4, "achievement", 3, create_role_name="💬 Pipelette", create_role_color=16751440)],
            stats={7: {"achievements": [3]}}, roles=roles)
    e.notifications = created
    return e


def test_achievement_unlock_creates_role_records_id_and_assigns(env, monkeypatch):
    async def scenario():
        e = _notifier_env(env, monkeypatch)
        member = e.guild.member(7)
        await notifier_module.AchievementsNotifier(e.bot).notify(7, 3)
        return e, member

    e, member = run(scenario)
    assert e.guild.created == [("💬 Pipelette", 16751440)]
    new_id = e.guild.roles[-1].id
    assert e.db.rules[0]["role_id"] == new_id
    assert member.calls == [("add", new_id)]
    assert e.notifications == [(7, "achievement", "Achievement débloqué : Pipelette", "d", 3)]
    assert ("role", "create") in [(r["kind"], r["action"]) for r in e.records]


def test_achievement_notification_survives_engine_error(env, monkeypatch, caplog):
    async def scenario():
        e = _notifier_env(env, monkeypatch)
        e.guild.member(7)

        async def boom(member):
            raise RuntimeError("moteur en panne")

        e.engine.evaluate_member = boom
        await notifier_module.AchievementsNotifier(e.bot).notify(7, 3)
        return e

    with caplog.at_level(logging.ERROR, logger=notifier_module.__name__):
        e = run(scenario)
    assert e.notifications == [(7, "achievement", "Achievement débloqué : Pipelette", "d", 3)]
    assert any("moteur" in r.getMessage() for r in caplog.records)


def test_achievement_unlock_reuses_existing_role_with_same_name(env, monkeypatch):
    existing = FakeRole(77, "💬 Pipelette")

    async def scenario():
        e = _notifier_env(env, monkeypatch, roles=[existing])
        member = e.guild.member(7)
        await notifier_module.AchievementsNotifier(e.bot).notify(7, 3)
        return e, member

    e, member = run(scenario)
    assert e.guild.created == []
    assert e.db.rules[0]["role_id"] == 77
    assert member.calls == [("add", 77)]


def test_resolved_rule_keeps_only_role_id(env, monkeypatch):
    """I1 : une règle résolue n'a plus de create_role_name (sinon web-api la refuse en 422)."""
    async def scenario():
        e = _notifier_env(env, monkeypatch)
        member = e.guild.member(7)
        await notifier_module.AchievementsNotifier(e.bot).notify(7, 3)
        return e

    e = run(scenario)
    row = e.db.rules[0]
    assert row["role_id"] is not None
    assert row["create_role_name"] is None and row["create_role_color"] is None
    rule = e.engine._rules[0]
    assert rule.create_role_name is None and rule.create_role_color is None


@pytest.mark.parametrize("homonym", [
    FakeRole(77, "💬 Pipelette", assignable=False),
    FakeRole(77, "💬 Pipelette", managed=True),
])
def test_achievement_unlock_ignores_unmanageable_homonym(env, monkeypatch, caplog, homonym):
    """C1 : un rôle de même nom au-dessus du bot (ou d'intégration) n'est ni réutilisé ni doublé."""
    async def scenario():
        e = _notifier_env(env, monkeypatch, roles=[homonym])
        member = e.guild.member(7)
        await notifier_module.AchievementsNotifier(e.bot).notify(7, 3)
        await e.engine.evaluate_member(member)
        return e, member

    with caplog.at_level(logging.WARNING, logger=engine_module.__name__):
        e, member = run(scenario)
    assert e.guild.created == []
    assert e.db.rules[0]["role_id"] is None
    assert member.calls == []
    assert len([r for r in caplog.records if "Pipelette" in r.getMessage()]) == 1


# ── Aperçu et application ────────────────────────────────────────────────────

def _preview_env(env):
    role = FakeRole(60, "Niv 5")
    e = env([rule_row(1, "level", 5, role_id=60, remove_when_lost=True)],
            stats={1: {"level": 6}, 2: {"level": 2}, 3: {"level": 7}}, roles=[role])
    e.a, e.b, e.c = e.guild.member(1), e.guild.member(2, [role]), e.guild.member(3, [role])
    return e


def test_preview_lists_gain_and_lose_without_changes(env):
    async def scenario():
        e = _preview_env(env)
        return e, await e.engine.preview(1)

    e, result = run(scenario)
    assert result == {"gain": [1], "lose": [2], "missing_role": False}
    assert e.a.calls == e.b.calls == e.c.calls == []
    assert e.records == []
    assert e.db.executed == []


def test_apply_reconciles_rule_and_counts(env):
    async def scenario():
        e = _preview_env(env)
        return e, await e.engine.apply(1)

    e, result = run(scenario)
    assert result == {"gain": [1], "lose": [2], "missing_role": False, "added": 1, "removed": 1,
                      "skipped": 0}
    assert e.a.calls == [("add", 60)] and e.b.calls == [("remove", 60)] and e.c.calls == []


def test_stats_read_in_one_query_per_batch_of_500(env):
    async def scenario():
        e = env([rule_row(1, "level", 5, role_id=60)], roles=[FakeRole(60, "Niv 5")])
        for uid in range(1, 502):
            e.guild.member(uid)
        await e.engine.preview(1)
        return e

    e = run(scenario)
    assert [len(c) for c in e.db.stats_calls] == [500, 1]


def test_deleted_role_marks_missing_and_warns_once(env, caplog):
    async def scenario():
        e = env([rule_row(1, "voice_hours", 100, role_id=999)], stats={7: {"voice_seconds": 200 * 3600}})
        member = e.guild.member(7)
        first = await e.engine.evaluate_member(member)
        second = await e.engine.evaluate_member(member)
        return member, first, second, await e.engine.preview(1)

    with caplog.at_level(logging.WARNING, logger=engine_module.__name__):
        member, first, second, preview = run(scenario)
    assert first == second == ([], [])
    assert member.calls == []
    assert preview["missing_role"] is True
    warnings = [r for r in caplog.records if "introuvable" in r.getMessage()]
    assert len(warnings) == 1


def test_unmanageable_role_is_missing_and_untouched(env):
    async def scenario():
        e = env([rule_row(1, "level", 5, role_id=60)], stats={7: {"level": 9}},
                roles=[FakeRole(60, "Au-dessus du bot", assignable=False)])
        member = e.guild.member(7)
        return member, await e.engine.evaluate_member(member), await e.engine.preview(1)

    member, result, preview = run(scenario)
    assert result == ([], []) and member.calls == []
    assert preview["missing_role"] is True


# ── Anciens chemins codés en dur ─────────────────────────────────────────────

def test_hardcoded_role_paths_are_gone():
    assert not hasattr(xp_module, "LEVEL_ROLE_KEYS")
    assert not hasattr(xp_module.XPCog, "_grant_level_role")
    voice_src = inspect.getsource(voice_module)
    assert "role_batman" not in voice_src
    assert "get_role" not in voice_src
    assert not hasattr(notifier_module.AchievementsNotifier, "backfill_roles")
    assert not hasattr(notifier_module.AchievementsNotifier, "_ensure_role")


def test_no_mass_reconciliation_for_preview_rules(env):
    """Règles amorcées (reconcile = false) : la boucle périodique ne touche à rien."""
    async def scenario():
        e = env([rule_row(1, "level", 5, role_id=60)], stats={7: {"level": 9}},
                roles=[FakeRole(60, "Niv 5")])
        member = e.guild.member(7)
        await e.engine.reconcile_loop.coro(e.engine)
        return member

    member = run(scenario)
    assert member.calls == []
