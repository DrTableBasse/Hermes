"""API interne : rôles, rôles des membres, lots et règles (étape 3, tâche 3)."""
import asyncio
import os
import sys
import time
import types
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import discord  # noqa: E402
import pytest  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

try:
    import prometheus_client  # noqa: F401
    import api  # noqa: E402
except ImportError:
    _stub = types.ModuleType("prometheus_client")
    _stub.CONTENT_TYPE_LATEST = "text/plain"
    _stub.generate_latest = lambda *a, **k: b""
    sys.modules["prometheus_client"] = _stub
    try:
        import api  # noqa: E402
    finally:
        del sys.modules["prometheus_client"]

TOKEN = "jeton-de-test"
REASON = "via le site par Alice"


class FakeRole:
    def __init__(self, rid, name, position, *, managed=False, default=False, color=0):
        self.id, self.name, self.position = rid, name, position
        self.managed, self._default = managed, default
        self.color = SimpleNamespace(value=color)
        self.members = []
        self.edits = []
        self.deleted_reason = None

    def is_default(self):
        return self._default

    async def edit(self, *, reason=None, **changes):
        self.edits.append((changes, reason))
        if "name" in changes:
            self.name = changes["name"]
        if "position" in changes:
            self.position = changes["position"]
        return self

    async def delete(self, *, reason=None):
        self.deleted_reason = reason


class FakeMember:
    def __init__(self, mid, roles, *, name=None, bot=False, fail=False):
        self.id, self.bot, self.fail = mid, bot, fail
        self.display_name = name or f"membre{mid}"
        self.roles = list(roles)
        self.calls = []

    async def add_roles(self, role, *, reason=None):
        self.calls.append(("add", role.id, reason))
        if self.fail:
            raise discord.HTTPException(SimpleNamespace(status=500, reason="boom"), "boom")
        self.roles.append(role)
        role.members.append(self)

    async def remove_roles(self, role, *, reason=None):
        self.calls.append(("remove", role.id, reason))
        self.roles.remove(role)
        role.members.remove(self)


class FakeGuild:
    owner_id = 999

    def __init__(self):
        self.everyone = FakeRole(1, "@everyone", 0, default=True)
        self.membre = FakeRole(10, "Membre", 1)
        self.vip = FakeRole(15, "VIP", 2)
        self.integration = FakeRole(20, "Bot Musique", 3, managed=True)
        self.bot_role = FakeRole(30, "Hermes", 5, managed=True)
        self.admin = FakeRole(40, "Admin", 8)
        self.roles = [self.everyone, self.membre, self.vip, self.integration, self.bot_role, self.admin]
        self.me = SimpleNamespace(top_role=self.bot_role)
        self._members = {}
        self.created = []

    def add_member(self, member):
        self._members[member.id] = member
        for r in member.roles:
            r.members.append(member)
        return member

    def get_member(self, user_id):
        return self._members.get(user_id)

    async def fetch_member(self, user_id):
        raise discord.NotFound(SimpleNamespace(status=404, reason="Not Found"), "Unknown Member")

    def get_role(self, role_id):
        return next((r for r in self.roles if r.id == role_id), None)

    async def create_role(self, *, name, colour, hoist, mentionable, reason):
        role = FakeRole(100 + len(self.created), name, 1, color=colour.value)
        role.hoist, role.mentionable = hoist, mentionable
        self.created.append((role, reason))
        self.roles.append(role)
        return role


class FakeEngine:
    def __init__(self):
        self.reloads = 0
        self.applied = []

    async def reload(self):
        self.reloads += 1

    async def _find_rule(self, rule_id):
        if rule_id != 7:
            raise KeyError(rule_id)

    async def preview(self, rule_id):
        await self._find_rule(rule_id)
        return {"gain": [42, 43], "lose": [44], "missing_role": False}

    async def apply(self, rule_id):
        self.applied.append(rule_id)
        return {"gain": [42, 43], "lose": [44], "missing_role": False, "added": 2, "removed": 0}


@pytest.fixture
def env(monkeypatch):
    guild = FakeGuild()
    engine = FakeEngine()
    bot = SimpleNamespace(get_cog=lambda name: engine if name == "RoleEngine" else None)
    monkeypatch.setattr(api, "BOT_API_TOKEN", TOKEN)
    monkeypatch.setattr(api, "_get_guild", lambda: guild)
    monkeypatch.setattr(api, "_bot", bot)
    monkeypatch.setattr(api, "_jobs", {})
    with TestClient(api.app) as client:  # contexte : la boucle survit entre requêtes (tâches de fond)
        client.headers["Authorization"] = f"Bearer {TOKEN}"
        yield SimpleNamespace(http=client, guild=guild, engine=engine)


def _wait_job(http, job_id, timeout=2.0):
    deadline = time.monotonic() + timeout
    while True:
        body = http.get(f"/discord/jobs/{job_id}").json()
        if body["state"] != "running" or time.monotonic() > deadline:
            return body
        time.sleep(0.01)


def _delete(http, url, body):
    return http.request("DELETE", url, json=body)


# ── Liste enrichie ───────────────────────────────────────────────────────────

def test_roles_list_exposes_member_count_and_below_bot(env):
    env.guild.add_member(FakeMember(42, [env.guild.everyone, env.guild.vip]))
    env.guild.add_member(FakeMember(43, [env.guild.everyone, env.guild.vip]))
    roles = {r["id"]: r for r in env.http.get("/discord/roles").json()["roles"]}
    assert "1" not in roles  # @everyone exclu
    assert roles["15"] == {"id": "15", "name": "VIP", "color": 0, "position": 2,
                           "managed": False, "members": 2, "below_bot": True}
    assert roles["30"]["below_bot"] is False  # le rôle du bot lui-même
    assert roles["40"]["below_bot"] is False


# ── Création, modification, suppression ──────────────────────────────────────

def test_create_role_below_bot_with_site_reason(env):
    r = env.http.post("/discord/roles", json={"name": "Nouveau", "color": 0xFF0000,
                                               "hoist": True, "mentionable": False,
                                               "actor_name": "Alice"})
    assert r.status_code == 200
    role, reason = env.guild.created[0]
    assert reason == REASON
    assert (role.name, role.color.value, role.hoist, role.mentionable) == ("Nouveau", 0xFF0000, True, False)
    body = r.json()
    assert body["name"] == "Nouveau" and body["below_bot"] is True and body["members"] == 0


@pytest.mark.parametrize("payload", [
    {"name": ""}, {"name": "x" * 101}, {"name": "ok", "color": 0x1000000}, {"name": "ok", "color": -1},
])
def test_create_role_rejects_invalid_fields(env, payload):
    r = env.http.post("/discord/roles", json={**payload, "actor_name": "Alice"})
    assert r.status_code == 422
    assert env.guild.created == []


def test_create_role_requires_actor_name(env):
    assert env.http.post("/discord/roles", json={"name": "Nouveau"}).status_code == 422


@pytest.mark.parametrize("role_id,fragment", [
    (1, "@everyone"), (20, "intégration"), (30, "intégration"),  # le rôle du bot est managed
    (40, "sous le rôle le plus haut du bot"),
])
def test_unmanageable_roles_are_refused_in_french(env, role_id, fragment):
    responses = [
        env.http.patch(f"/discord/roles/{role_id}", json={"name": "x", "actor_name": "Alice"}),
        _delete(env.http, f"/discord/roles/{role_id}", {"actor_name": "Alice"}),
        env.http.post(f"/discord/roles/{role_id}/bulk",
                      json={"action": "add", "user_ids": ["42"], "actor_name": "Alice"}),
    ]
    for r in responses:
        assert r.status_code == 403
        assert fragment in r.json()["detail"]
    role = env.guild.get_role(role_id)
    assert role.edits == [] and role.deleted_reason is None


def test_unknown_role_is_404(env):
    r = env.http.patch("/discord/roles/555", json={"name": "x", "actor_name": "Alice"})
    assert r.status_code == 404


def test_update_role_bounds_position_below_bot(env):
    r = env.http.patch("/discord/roles/15", json={"name": "VIP+", "position": 50, "actor_name": "Alice"})
    assert r.status_code == 200
    changes, reason = env.guild.vip.edits[0]
    assert changes["position"] == 4  # bot en 5 : strictement en dessous
    assert changes["name"] == "VIP+"
    assert reason == REASON
    assert r.json()["position"] == 4


def test_update_role_only_sends_given_fields(env):
    env.http.patch("/discord/roles/15", json={"hoist": True, "actor_name": "Alice"})
    assert env.guild.vip.edits == [({"hoist": True}, REASON)]


def test_delete_role_with_site_reason(env):
    r = _delete(env.http, "/discord/roles/15", {"actor_name": "Alice"})
    assert r.status_code == 200
    assert env.guild.vip.deleted_reason == REASON


def test_discord_forbidden_becomes_french_403(env):
    async def forbidden(**kwargs):
        raise discord.Forbidden(SimpleNamespace(status=403, reason="Forbidden"), "Missing Permissions")
    env.guild.vip.delete = forbidden
    r = _delete(env.http, "/discord/roles/15", {"actor_name": "Alice"})
    assert r.status_code == 403
    assert "Permission refusée" in r.json()["detail"]


# ── Rôle d'un membre ─────────────────────────────────────────────────────────

def test_add_and_remove_member_role(env):
    m = env.guild.add_member(FakeMember(42, [env.guild.everyone]))
    assert env.http.post("/discord/members/42/roles/15", json={"actor_name": "Alice"}).status_code == 200
    assert env.guild.vip in m.roles
    assert _delete(env.http, "/discord/members/42/roles/15", {"actor_name": "Alice"}).status_code == 200
    assert env.guild.vip not in m.roles
    assert m.calls == [("add", 15, REASON), ("remove", 15, REASON)]


def test_member_role_refuses_managed_and_unknown_member(env):
    env.guild.add_member(FakeMember(42, [env.guild.everyone]))
    assert env.http.post("/discord/members/42/roles/20", json={"actor_name": "Alice"}).status_code == 403
    assert env.http.post("/discord/members/77/roles/15", json={"actor_name": "Alice"}).status_code == 404


# ── Lots ─────────────────────────────────────────────────────────────────────

def test_bulk_add_three_members_job_done(env):
    members = [env.guild.add_member(FakeMember(i, [env.guild.everyone])) for i in (42, 43, 44)]
    r = env.http.post("/discord/roles/15/bulk",
                      json={"action": "add", "user_ids": ["42", "43", "44"], "actor_name": "Alice"})
    assert r.status_code == 200
    job = _wait_job(env.http, r.json()["job_id"])
    assert job == {"state": "done", "done": 3, "total": 3, "errors": 0}
    for m in members:
        assert env.guild.vip in m.roles
        assert m.calls == [("add", 15, REASON)]


def test_bulk_counts_errors_and_skips_holders(env):
    env.guild.add_member(FakeMember(42, [env.guild.everyone, env.guild.vip]))  # déjà porteur
    env.guild.add_member(FakeMember(43, [env.guild.everyone], fail=True))     # échec Discord
    r = env.http.post("/discord/roles/15/bulk",
                      json={"action": "add", "user_ids": ["42", "43", "99"], "actor_name": "Alice"})
    job = _wait_job(env.http, r.json()["job_id"])
    assert job == {"state": "done", "done": 3, "total": 3, "errors": 2}  # 43 échoue, 99 absent
    assert env.guild.get_member(42).calls == []


def test_bulk_remove_from_role_holders(env):
    a = env.guild.add_member(FakeMember(42, [env.guild.everyone, env.guild.membre, env.guild.vip]))
    b = env.guild.add_member(FakeMember(43, [env.guild.everyone, env.guild.membre, env.guild.vip]))
    c = env.guild.add_member(FakeMember(44, [env.guild.everyone, env.guild.vip]))
    r = env.http.post("/discord/roles/15/bulk",
                      json={"action": "remove", "from_role_id": "10", "actor_name": "Alice"})
    job = _wait_job(env.http, r.json()["job_id"])
    assert job == {"state": "done", "done": 2, "total": 2, "errors": 0}
    assert env.guild.vip not in a.roles and env.guild.vip not in b.roles
    assert env.guild.vip in c.roles


def test_bulk_over_500_user_ids_is_422(env):
    r = env.http.post("/discord/roles/15/bulk",
                      json={"action": "add", "user_ids": [str(i) for i in range(1, 502)],
                            "actor_name": "Alice"})
    assert r.status_code == 422
    assert api._jobs == {}


def test_bulk_from_role_over_500_members_is_422(env):
    for i in range(1, 502):
        env.guild.add_member(FakeMember(1000 + i, [env.guild.everyone, env.guild.membre]))
    r = env.http.post("/discord/roles/15/bulk",
                      json={"action": "add", "from_role_id": "10", "actor_name": "Alice"})
    assert r.status_code == 422
    assert "500" in r.json()["detail"]


@pytest.mark.parametrize("body", [
    {"action": "add"},
    {"action": "add", "user_ids": ["42"], "from_role_id": "10"},
    {"action": "toggle", "user_ids": ["42"]},
    {"action": "add", "user_ids": ["pas-un-id"]},
])
def test_bulk_invalid_body_is_422(env, body):
    assert env.http.post("/discord/roles/15/bulk", json={**body, "actor_name": "Alice"}).status_code == 422


def test_unknown_job_is_404(env):
    r = env.http.get("/discord/jobs/inconnu")
    assert r.status_code == 404


def test_bulk_cancelled_job_is_interrupted_with_progress(env):
    gate = {}

    class SlowMember(FakeMember):
        async def add_roles(self, role, *, reason=None):
            if self.id == 43:
                gate["event"] = asyncio.Event()
                await gate["event"].wait()  # bloqué jusqu'à l'annulation
            await super().add_roles(role, reason=reason)

    for i in (42, 43, 44):
        env.guild.add_member(SlowMember(i, [env.guild.everyone]))
    job_id = env.http.post("/discord/roles/15/bulk",
                           json={"action": "add", "user_ids": ["42", "43", "44"],
                                 "actor_name": "Alice"}).json()["job_id"]
    deadline = time.monotonic() + 2
    while "event" not in gate and time.monotonic() < deadline:
        time.sleep(0.01)

    async def cancel_all():  # arrêt du bot : les tâches de fond sont annulées
        tasks = list(api._job_tasks)
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    env.http.portal.call(cancel_all)
    job = env.http.get(f"/discord/jobs/{job_id}").json()
    assert job == {"state": "interrupted", "done": 1, "total": 3, "errors": 0}


def test_failed_job_state(env):
    async def boom(job):
        raise RuntimeError("panne")

    async def start():
        return api._start_job(1, boom)

    job_id = env.http.portal.call(start)
    assert _wait_job(env.http, job_id)["state"] == "failed"


def test_finished_jobs_are_purged_after_one_hour(env):
    api._jobs["vieux"] = {"state": "done", "done": 1, "total": 1, "errors": 0,
                          "finished_at": time.monotonic() - api.JOB_TTL_S - 1}
    api._jobs["recent"] = {"state": "done", "done": 1, "total": 1, "errors": 0,
                           "finished_at": time.monotonic()}
    api._jobs["en_cours"] = {"state": "running", "done": 0, "total": 1, "errors": 0,
                             "finished_at": None}
    api._purge_jobs()
    assert set(api._jobs) == {"recent", "en_cours"}


def test_jobs_dict_is_bounded(env, monkeypatch):
    monkeypatch.setattr(api, "JOBS_MAX", 2)
    api._jobs["a"] = {"state": "running", "finished_at": None}
    api._jobs["b"] = {"state": "running", "finished_at": None}
    env.guild.add_member(FakeMember(42, [env.guild.everyone]))
    r = env.http.post("/discord/roles/15/bulk",
                      json={"action": "add", "user_ids": ["42"], "actor_name": "Alice"})
    assert r.status_code == 429
    api._jobs["b"] = {"state": "done", "finished_at": time.monotonic()}  # un terminé : il cède la place
    r = env.http.post("/discord/roles/15/bulk",
                      json={"action": "add", "user_ids": ["42"], "actor_name": "Alice"})
    assert r.status_code == 200
    assert "b" not in api._jobs and "a" in api._jobs


# ── Règles ───────────────────────────────────────────────────────────────────

def test_role_rules_reload(env):
    r = env.http.post("/role-rules/reload")
    assert r.status_code == 200 and env.engine.reloads == 1


def test_preview_shape(env):
    env.guild.add_member(FakeMember(42, [env.guild.everyone], name="Alice"))
    env.guild.add_member(FakeMember(44, [env.guild.everyone], name="Bob"))
    r = env.http.get("/role-rules/7/preview")
    assert r.status_code == 200
    assert r.json() == {
        "gain": [{"id": "42", "name": "Alice"}, {"id": "43", "name": None}],
        "lose": [{"id": "44", "name": "Bob"}],
        "missing_role": False,
    }


def test_preview_unknown_rule_is_404(env):
    assert env.http.get("/role-rules/8/preview").status_code == 404


def test_apply_runs_as_job(env):
    r = env.http.post("/role-rules/7/apply")
    assert r.status_code == 200
    job = _wait_job(env.http, r.json()["job_id"])
    assert job == {"state": "done", "done": 3, "total": 3, "errors": 1,
                   "added": 2, "removed": 0, "missing_role": False}
    assert env.engine.applied == [7]


def test_apply_unknown_rule_is_404(env):
    assert env.http.post("/role-rules/8/apply").status_code == 404
    assert env.engine.applied == []


def test_rules_engine_missing_is_503(env, monkeypatch):
    monkeypatch.setattr(api, "_bot", SimpleNamespace(get_cog=lambda name: None))
    assert env.http.post("/role-rules/reload").status_code == 503


def test_new_routes_require_token(env):
    bad = {"Authorization": "Bearer faux"}
    assert env.http.post("/discord/roles", json={"name": "x", "actor_name": "A"}, headers=bad).status_code == 401
    assert env.http.get("/discord/jobs/x", headers=bad).status_code == 401
    assert env.http.post("/role-rules/reload", headers=bad).status_code == 401
