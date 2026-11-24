"""Rôle de bump = règle automatique (étape 4, tâche 1) : amorçage, attribution par le moteur."""
import inspect
from types import SimpleNamespace as N

import pytest

from cogs.system import bump_tracker as tracker_module
from cogs.system import role_engine as engine_module
from utils import settings

# Réutilise les faux Discord et le banc d'essai du moteur de règles.
from tests.test_role_engine import FakeRole, env, rule_row, run  # noqa: F401


class BumpDB:
    """FakeDB du moteur + SQL d'amorçage : marqueur ``bump_rule_seeded`` et insertion de la règle."""

    def __init__(self, base):
        self._base = base
        self.markers = set()

    def __getattr__(self, name):
        return getattr(self._base, name)

    def _has_bumps(self):
        return any(r["condition_type"] == "bumps" for r in self._base.rules)

    async def fetchval(self, sql, *args):
        if sql.startswith("SELECT 1 FROM bot_settings"):
            assert "bump_rule_seeded" in sql
            return 1 if "bump_rule_seeded" in self.markers else None
        # Un seul ordre SQL : règle + marqueur ensemble (atomique), gardé par NOT EXISTS.
        assert "INSERT INTO role_rules" in sql and "NOT EXISTS" in sql and "bump_rule_seeded" in sql
        role_id, threshold = args
        self.markers.add("bump_rule_seeded")
        if self._has_bumps():
            return None
        rules = self._base.rules
        rule = rule_row(max([r["id"] for r in rules] + [0]) + 1, "bumps", threshold, role_id=role_id)
        rules.append(rule)
        return rule["id"]

    async def execute(self, sql, *args):
        # Rôle non résolu mais règle déjà là : on pose seulement le marqueur.
        assert "bump_rule_seeded" in sql and "EXISTS" in sql
        if self._has_bumps():
            self.markers.add("bump_rule_seeded")


@pytest.fixture
def bump_env(env, monkeypatch):  # noqa: F811
    def make(rules=(), roles=(), stored=None, stats=None):
        e = env(list(rules), stats=stats, roles=roles)
        e.engine.db = BumpDB(e.db)
        monkeypatch.setattr(engine_module, "db_manager", e.engine.db)
        monkeypatch.setattr(settings, "_cache", dict(stored or {}))
        return e
    return make


def bumps_rules(e):
    return [r for r in e.db.rules if r["condition_type"] == "bumps"]


# ── Amorçage ─────────────────────────────────────────────────────────────────

def test_seed_creates_bump_rule_from_default_role_and_threshold(bump_env):
    async def scenario():
        e = bump_env(roles=[FakeRole(70, "Bumper Fou")])
        await e.engine.seed_bump_rule(e.guild)
        return e

    e = run(scenario)
    rules = bumps_rules(e)
    assert len(rules) == 1
    assert (rules[0]["role_id"], rules[0]["condition_value"]) == (70, "20")
    assert rules[0]["active"] is True and rules[0]["reconcile"] is False  # mode aperçu


def test_seed_uses_stored_role_and_threshold(bump_env):
    async def scenario():
        e = bump_env(roles=[FakeRole(71, "Autre")], stored={"bump_role": "71", "bump_role_threshold": "35"})
        await e.engine.seed_bump_rule(e.guild)
        return e

    e = run(scenario)
    assert [(r["role_id"], r["condition_value"]) for r in bumps_rules(e)] == [(71, "35")]


def test_seed_is_idempotent_across_restarts(bump_env):
    async def scenario():
        e = bump_env(roles=[FakeRole(70, "Bumper Fou")])
        await e.engine.seed_bump_rule(e.guild)
        await e.engine.seed_bump_rule(e.guild)  # redémarrage
        return e

    assert len(bumps_rules(run(scenario))) == 1


def test_seed_keeps_existing_bump_rule(bump_env):
    async def scenario():
        e = bump_env(rules=[rule_row(3, "bumps", 50, role_id=72)], roles=[FakeRole(70, "Bumper Fou")])
        await e.engine.seed_bump_rule(e.guild)
        return e

    rules = bumps_rules(run(scenario))
    assert [(r["id"], r["role_id"], r["condition_value"]) for r in rules] == [(3, 72, "50")]


def test_seed_creates_nothing_when_role_does_not_resolve(bump_env):
    async def scenario():
        e = bump_env(roles=[FakeRole(1, "Autre rôle")])  # aucun « Bumper Fou »
        await e.engine.seed_bump_rule(e.guild)
        e2 = bump_env(roles=[FakeRole(1, "Autre rôle")], stored={"bump_role": "999"})  # id disparu
        await e2.engine.seed_bump_rule(e2.guild)
        return e, e2

    e, e2 = run(scenario)
    assert bumps_rules(e) == [] and bumps_rules(e2) == []


def test_seed_runs_at_startup_after_settings_are_ready(bump_env, monkeypatch):
    src = inspect.getsource(engine_module.RoleEngine._before_reconcile)
    assert "settings.ready.wait()" in src and "seed_bump_rule" in src


# ── Attribution par le moteur ────────────────────────────────────────────────

def test_engine_gives_bump_role_at_threshold_only(bump_env):
    async def scenario():
        e = bump_env(rules=[rule_row(1, "bumps", 20, role_id=70)],
                     roles=[FakeRole(70, "Bumper Fou")], stats={7: {"bumps": 20}, 8: {"bumps": 19}})
        at, below = e.guild.member(7), e.guild.member(8)
        await e.engine.evaluate_member(at)
        await e.engine.evaluate_member(below)
        return at, below

    at, below = run(scenario)
    assert at.calls == [("add", 70)]
    assert below.calls == []


def test_threshold_edit_applies_to_next_bump_without_other_setting(bump_env):
    async def scenario():
        e = bump_env(rules=[rule_row(1, "bumps", 20, role_id=70)],
                     roles=[FakeRole(70, "Bumper Fou")], stats={7: {"bumps": 25}})
        member = e.guild.member(7)
        e.db.rules[0]["condition_value"] = "30"  # seuil relevé depuis le site
        await e.engine.reload()
        await e.engine.evaluate_member(member)
        first = list(member.calls)
        e.db.rules[0]["condition_value"] = "10"  # puis abaissé
        await e.engine.reload()
        await e.engine.evaluate_member(member)
        return first, member

    first, member = run(scenario)
    assert first == []
    assert member.calls == [("add", 70)]


# ── bump_tracker : plus d'attribution codée en dur ───────────────────────────

class FakeAuthor:
    id = tracker_module.DISBOARD_ID


class Managers:
    def __init__(self, count):
        self.count = count
        self.added = []

    async def _noop(self, *a, **k):
        return []


def _install_managers(monkeypatch, count):
    import utils.database as database

    async def sync_member(*a, **k):
        return None

    async def increment(uid):
        return None

    async def update_progress(*a, **k):
        return []

    async def add_xp(*a, **k):
        return None

    async def get_count(uid):
        return count

    async def check_and_unlock(*a, **k):
        return []

    async def record_bump(*a, **k):
        return None

    monkeypatch.setattr(database, "voice_manager", N(sync_member=sync_member))
    monkeypatch.setattr(database, "bump_manager", N(increment=increment, get_count=get_count))
    monkeypatch.setattr(database, "quest_manager", N(update_progress=update_progress))
    monkeypatch.setattr(database, "xp_manager", N(add_xp=add_xp, XP_BUMP=5))
    monkeypatch.setattr(database, "achievement_manager", N(check_and_unlock=check_and_unlock))
    monkeypatch.setattr(database, "bump_reminder_manager", N(record_bump=record_bump))


def _bump_message(guild, member):
    import datetime as dt
    channel = N(id=10, mention="#bump")
    return N(channel=channel, author=FakeAuthor(), content="", guild=guild, id=555, embeds=[],
             created_at=dt.datetime(2026, 11, 24, tzinfo=dt.timezone.utc),
             interaction_metadata=N(user=member), interaction=None)


def test_bump_hits_threshold_role_comes_from_engine_not_tracker(bump_env, monkeypatch):
    async def scenario():
        bumper_role = FakeRole(70, "Bumper Fou")
        e = bump_env(rules=[rule_row(1, "bumps", 20, role_id=70)], roles=[bumper_role],
                     stats={7: {"bumps": 20}}, stored={"bump_channel": "10"})
        member = e.guild.member(7)
        member.display_avatar = None
        member.mention = "<@7>"

        async def fetch_member(_):
            return member

        e.guild.fetch_member = fetch_member
        _install_managers(monkeypatch, count=20)
        sent = []

        async def configured_channel(guild, key):
            return N(send=lambda embed: _send(sent, embed))

        async def _send(sent, embed):
            sent.append(embed)

        monkeypatch.setattr(settings, "configured_channel", configured_channel)
        monkeypatch.setattr(tracker_module, "hermes_embed", lambda **k: _Embed())
        cog = tracker_module.BumpTrackerCog(e.bot)
        await cog.on_message(_bump_message(e.guild, member))
        return e, member, sent

    e, member, sent = run(scenario)
    assert member.calls == [("add", 70)]  # une seule attribution, via le moteur
    assert [(r["kind"], r["action"], r["source"]) for r in e.records] == [("member_role", "add", "hermes")]
    assert any("Bumper Fou" in str(f) for f in sent[0].fields)  # l'embed annonce le rôle obtenu


class _Embed:
    def __init__(self):
        self.fields = []

    def add_field(self, name, value, inline=True):
        self.fields.append((name, value))

    def set_footer(self, **k):
        pass


def test_tracker_no_longer_hardcodes_bump_role():
    src = inspect.getsource(tracker_module)
    assert "bump_role" not in src and "add_roles" not in src
    assert "evaluate_member" in src


def test_seed_marks_seeding_with_the_rule(bump_env):
    async def scenario():
        e = bump_env(roles=[FakeRole(70, "Bumper Fou")])
        await e.engine.seed_bump_rule(e.guild)
        return e

    assert "bump_rule_seeded" in run(scenario).engine.db.markers


def test_deleted_rule_is_not_recreated_at_next_startup(bump_env):
    async def scenario():
        e = bump_env(roles=[FakeRole(70, "Bumper Fou")])
        await e.engine.seed_bump_rule(e.guild)      # premier démarrage
        e.db.rules[:] = []                          # l'admin supprime la règle
        await e.engine.seed_bump_rule(e.guild)      # redémarrage
        return e

    assert bumps_rules(run(scenario)) == []


def test_marker_blocks_seeding_even_without_any_bump_rule(bump_env):
    async def scenario():
        e = bump_env(roles=[FakeRole(70, "Bumper Fou")])
        e.engine.db.markers.add("bump_rule_seeded")
        await e.engine.seed_bump_rule(e.guild)
        return e

    assert bumps_rules(run(scenario)) == []


def test_existing_rule_gets_marked_even_if_role_does_not_resolve(bump_env):
    async def scenario():
        e = bump_env(rules=[rule_row(3, "bumps", 50, role_id=72)], roles=[FakeRole(1, "Autre")])
        await e.engine.seed_bump_rule(e.guild)
        return e

    assert "bump_rule_seeded" in run(scenario).engine.db.markers
