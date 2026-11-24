"""API interne : salons et modèles d'accès (étape 5, tâche 2) — serveur Discord simulé."""
import os
import sys
import types
from datetime import datetime, timezone
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

from utils import channels_api, settings  # noqa: E402

TOKEN = "jeton-de-test"
REASON = "via le site par Alice"
VIEW = discord.Permissions(view_channel=True).value


class FakeRole:
    def __init__(self, rid, name, position, *, default=False):
        self.id, self.name, self.position, self._default = rid, name, position, default

    def is_default(self):
        return self._default

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        return getattr(other, "id", None) == self.id


class FakeMember:
    def __init__(self, mid, top_role, name="membre"):
        self.id, self.top_role, self.display_name = mid, top_role, name

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        return getattr(other, "id", None) == self.id


class FakeChannel:
    def __init__(self, guild, cid, name, ctype, position, category=None, overwrites=None, hidden_from=()):
        self.guild, self.id, self.name, self.type, self.position = guild, cid, name, ctype, position
        self.category_id = category.id if category else None
        self.overwrites = dict(overwrites or {})
        self.hidden_from = set(hidden_from)
        self.edits, self.deleted_reason = [], None
        self.fail = None

    @property
    def channels(self):
        return [c for c in self.guild.channels if c.category_id == self.id]

    def permissions_for(self, member):
        return SimpleNamespace(view_channel=member.id not in self.hidden_from)

    async def edit(self, *, reason=None, **changes):
        if self.fail:
            raise self.fail
        self.edits.append((changes, reason))
        if "overwrites" in changes:
            self.overwrites = dict(changes["overwrites"])
        if "name" in changes:
            self.name = changes["name"]
        if "category" in changes:
            self.category_id = changes["category"].id if changes["category"] else None
        if "position" in changes:
            self.position = changes["position"]
        return self

    async def delete(self, *, reason=None):
        self.deleted_reason = reason
        self.guild.channels.remove(self)


def ow(allow=0, deny=0):
    return discord.PermissionOverwrite.from_pair(discord.Permissions(allow), discord.Permissions(deny))


class FakeGuild:
    owner_id = 999

    def __init__(self):
        self.default_role = FakeRole(1, "@everyone", 0, default=True)
        self.membre = FakeRole(10, "Membre", 1)
        self.vip = FakeRole(15, "VIP", 2)
        self.modo = FakeRole(20, "Modo", 4)
        self.admin = FakeRole(40, "Admin", 8)
        self.roles = [self.default_role, self.membre, self.vip, self.modo, self.admin]
        self.me = FakeMember(500, FakeRole(30, "Hermes", 6), "Hermes")
        self.alice = FakeMember(42, self.modo, "Alice")       # modératrice
        self.bob = FakeMember(43, self.membre, "Bob")         # simple membre
        self.owner = FakeMember(999, self.membre, "Proprio")
        self.tiers = FakeMember(77, self.membre, "Tiers")
        self._members = {m.id: m for m in (self.me, self.alice, self.bob, self.owner, self.tiers)}
        T = discord.ChannelType
        self.channels = []
        self.cat = self._add(100, "Jeux", T.category, 1)
        self.general = self._add(101, "general", T.text, 0)
        self.child1 = self._add(102, "minecraft", T.text, 0, self.cat,
                                {self.tiers: ow(allow=VIEW)})
        self.child2 = self._add(103, "vocal-jeux", T.voice, 1, self.cat)
        self.staff = self._add(104, "staff", T.text, 2, None,
                               {self.default_role: ow(deny=VIEW), self.modo: ow(allow=VIEW)},
                               hidden_from={self.bob.id})
        self.empty_cat = self._add(105, "Vide", T.category, 3)
        self.created = []

    def _add(self, cid, name, ctype, position, category=None, overwrites=None, hidden_from=()):
        ch = FakeChannel(self, cid, name, ctype, position, category, overwrites, hidden_from)
        self.channels.append(ch)
        return ch

    def get_member(self, mid):
        return self._members.get(mid)

    async def fetch_member(self, mid):
        raise discord.NotFound(SimpleNamespace(status=404, reason="Not Found"), "Unknown Member")

    def get_role(self, rid):
        return next((r for r in self.roles if r.id == rid), None)

    def get_channel(self, cid):
        return next((c for c in self.channels if c.id == cid), None)

    async def _create(self, name, ctype, category, reason):
        ch = self._add(600 + len(self.created), name, ctype, 9, category)
        self.created.append((ch, reason))
        return ch

    async def create_category(self, name, *, reason=None):
        return await self._create(name, discord.ChannelType.category, None, reason)

    async def create_text_channel(self, name, *, category=None, reason=None, news=False):
        t = discord.ChannelType.news if news else discord.ChannelType.text
        return await self._create(name, t, category, reason)

    async def create_voice_channel(self, name, *, category=None, reason=None):
        return await self._create(name, discord.ChannelType.voice, category, reason)

    async def create_forum(self, name, *, category=None, reason=None):
        return await self._create(name, discord.ChannelType.forum, category, reason)


@pytest.fixture
def env(monkeypatch):
    guild = FakeGuild()
    memo: dict[int, dict] = {}

    async def load():
        return dict(memo)

    async def save(cid, template, roles, applied_by):
        memo[cid] = {"channel_id": cid, "template": template, "roles": list(roles),
                     "applied_by": applied_by, "applied_at": datetime(2026, 11, 24, tzinfo=timezone.utc)}

    async def delete(cid):
        memo.pop(cid, None)

    staff_roles = [guild.modo]
    monkeypatch.setattr(api, "BOT_API_TOKEN", TOKEN)
    monkeypatch.setattr(api, "_get_guild", lambda: guild)
    monkeypatch.setattr(channels_api, "load_templates", load)
    monkeypatch.setattr(channels_api, "save_template", save)
    monkeypatch.setattr(channels_api, "delete_template", delete)
    monkeypatch.setattr(settings, "get_roles", lambda g, key: list(staff_roles) if key == "staff_roles" else [])
    client = TestClient(api.app)
    client.headers["Authorization"] = f"Bearer {TOKEN}"
    return SimpleNamespace(guild=guild, client=client, memo=memo, staff_roles=staff_roles)


def ids(overwrites):
    return {t.id: o.pair() for t, o in overwrites.items()}


def preview(env, cid, template, roles=(), actor=42, sync=False):
    return env.client.post(f"/discord/channels/{cid}/template/preview", json={
        "template": template, "roles": [str(r) for r in roles], "sync_children": sync,
        "actor_id": str(actor)})


def apply(env, cid, template, token, roles=(), actor=42, sync=False):
    return env.client.post(f"/discord/channels/{cid}/template/apply", json={
        "template": template, "roles": [str(r) for r in roles], "sync_children": sync,
        "actor_id": str(actor), "actor_name": "Alice", "token": token})


# ── Arbre ────────────────────────────────────────────────────────────────────

def test_tree_order_fields_and_visibility(env):
    env.memo[104] = {"template": "staff", "roles": [20], "applied_by": 42,
                     "applied_at": datetime(2026, 11, 24, tzinfo=timezone.utc)}
    r = env.client.get("/discord/channels/tree", params={"actor_id": 43})
    assert r.status_code == 200
    rows = r.json()["channels"]
    assert [c["name"] for c in rows] == ["general", "staff", "Jeux", "minecraft", "vocal-jeux", "Vide"]
    by = {c["name"]: c for c in rows}
    assert by["minecraft"]["parent_id"] == "100" and by["minecraft"]["overwrites"] == 1
    assert by["vocal-jeux"]["type"] == "voice" and by["Jeux"]["type"] == "category"
    assert by["staff"]["visible_to_actor"] is False and by["general"]["visible_to_actor"] is True
    assert by["staff"]["template"]["template"] == "staff" and by["staff"]["template"]["roles"] == ["20"]
    assert by["general"]["template"] is None


def test_tree_owner_sees_everything_and_absent_actor_is_403(env):
    env.guild.staff.hidden_from.add(999)
    rows = env.client.get("/discord/channels/tree", params={"actor_id": 999}).json()["channels"]
    assert all(c["visible_to_actor"] for c in rows)
    assert env.client.get("/discord/channels/tree", params={"actor_id": 12345}).status_code == 403


def test_requires_token(env):
    r = env.client.get("/discord/channels/tree", params={"actor_id": 42},
                       headers={"Authorization": "Bearer faux"})
    assert r.status_code == 401


# ── Création, modification, suppression ─────────────────────────────────────

def test_create_channels_of_each_type(env):
    c = env.client
    r = c.post("/discord/channels", json={"name": "annonces", "type": "announcement",
                                          "parent_id": "100", "actor_id": "42", "actor_name": "Alice"})
    assert r.status_code == 200 and r.json()["type"] == "announcement"
    ch, reason = env.guild.created[-1]
    assert ch.type == discord.ChannelType.news and ch.category_id == 100 and reason == REASON
    assert c.post("/discord/channels", json={"name": "Nouvelle", "type": "category",
                                             "actor_id": "42", "actor_name": "Alice"}).status_code == 200
    assert env.guild.created[-1][0].type == discord.ChannelType.category
    assert c.post("/discord/channels", json={"name": "f", "type": "forum",
                                             "actor_id": "42", "actor_name": "Alice"}).json()["type"] == "forum"


def test_create_rejects_bad_parent_and_type(env):
    c = env.client
    assert c.post("/discord/channels", json={"name": "x", "type": "category", "parent_id": "100",
                                             "actor_id": "42", "actor_name": "Alice"}).status_code == 422
    assert c.post("/discord/channels", json={"name": "x", "type": "text", "parent_id": "101",
                                             "actor_id": "42", "actor_name": "Alice"}).status_code == 404
    assert c.post("/discord/channels", json={"name": "x", "type": "stage",
                                             "actor_id": "42", "actor_name": "Alice"}).status_code == 422
    assert c.post("/discord/channels", json={"name": "", "type": "text",
                                             "actor_id": "42", "actor_name": "Alice"}).status_code == 422


def test_patch_rename_move_and_leave_category(env):
    c = env.client
    r = c.patch("/discord/channels/101", json={"name": "accueil", "parent_id": "100", "actor_id": "42", "actor_name": "Alice"})
    assert r.status_code == 200 and r.json()["parent_id"] == "100"
    assert env.guild.general.edits[-1] == ({"name": "accueil", "category": env.guild.cat}, REASON)
    r = c.patch("/discord/channels/101", json={"parent_id": None, "actor_id": "42", "actor_name": "Alice"})
    assert r.json()["parent_id"] is None
    # parent_id absent : la catégorie n'est pas touchée
    c.patch("/discord/channels/102", json={"position": 3, "actor_id": "42", "actor_name": "Alice"})
    assert env.guild.child1.edits[-1][0] == {"position": 3}


def test_patch_refused_when_actor_does_not_see_channel(env):
    r = env.client.patch("/discord/channels/104", json={"name": "x", "actor_id": "43", "actor_name": "Bob"})
    assert r.status_code == 403 and env.guild.staff.edits == []


def test_delete_non_empty_category_is_409(env):
    r = env.client.request("DELETE", "/discord/channels/100", json={"actor_id": "42", "actor_name": "Alice"})
    assert r.status_code == 409 and "Videz d'abord la catégorie" in r.json()["detail"]
    assert env.guild.cat in env.guild.channels


def test_delete_channel_and_forget_template(env):
    env.memo[105] = {"template": "public", "roles": [], "applied_by": 1, "applied_at": None}
    r = env.client.request("DELETE", "/discord/channels/105", json={"actor_id": "42", "actor_name": "Alice"})
    assert r.status_code == 200 and env.guild.empty_cat.deleted_reason == REASON
    assert 105 not in env.memo


def test_discord_forbidden_is_translated(env):
    env.guild.general.fail = discord.Forbidden(SimpleNamespace(status=403, reason="Forbidden"), "no")
    r = env.client.patch("/discord/channels/101", json={"name": "x", "actor_id": "42", "actor_name": "Alice"})
    assert r.status_code == 403 and "le bot n'a pas les droits" in r.json()["detail"]


# ── Modèles : contrôles d'accès ──────────────────────────────────────────────

def test_public_on_hidden_staff_channel_by_member_who_cannot_see_is_403(env):
    r = preview(env, 104, "public", actor=43)
    assert r.status_code == 403 and "staff" not in r.text
    r = apply(env, 104, "public", "nimporte", actor=43)
    assert r.status_code == 403 and env.guild.staff.edits == [] and "staff" not in r.text


def test_owner_is_exempt_from_visibility(env):
    env.guild.staff.hidden_from.add(999)
    assert preview(env, 104, "public", actor=999).status_code == 200


def test_absent_actor_is_403(env):
    assert preview(env, 101, "public", actor=12345).status_code == 403


@pytest.mark.parametrize("template", ["role_required", "announcements"])
def test_role_above_actor_is_403(env, template):
    # Alice : rôle le plus haut Modo (4) ; Admin (8) au-dessus, Modo lui-même pas strictement dessous.
    assert preview(env, 101, template, roles=[40]).status_code == 403
    assert preview(env, 101, template, roles=[20]).status_code == 403
    assert preview(env, 101, template, roles=[15]).status_code == 200
    assert preview(env, 101, template, roles=[40], actor=999).status_code == 200  # propriétaire


def test_role_template_needs_roles_and_rejects_everyone(env):
    assert preview(env, 101, "role_required").status_code == 422
    assert preview(env, 101, "role_required", roles=[1]).status_code == 422
    assert preview(env, 101, "role_required", roles=[555]).status_code == 404


def test_cannot_remove_overwrite_of_role_above_actor(env):
    # Le salon staff porte une surcharge Modo ; Bob est sous Modo mais voit le salon ici.
    env.guild.staff.hidden_from.clear()
    env.memo[104] = {"template": "staff", "roles": [20], "applied_by": 1, "applied_at": None}
    r = preview(env, 104, "public", actor=43)
    assert r.status_code == 403 and "Modo" in r.json()["detail"]
    assert preview(env, 104, "public", actor=999).status_code == 200


# ── Aperçu et application ────────────────────────────────────────────────────

def test_preview_lists_changes_and_apply_writes_them(env):
    g = env.guild
    r = preview(env, 102, "role_required", roles=[15])
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 1 and body["channels"][0]["name"] == "minecraft"
    changes = {c["target_name"]: c for c in body["channels"][0]["changes"]}
    assert changes["@everyone"]["action"] == "add"
    assert changes["@everyone"]["after"]["deny"] == ["view_channel"]
    assert "send_messages" in changes["VIP"]["after"]["allow"]
    assert changes["Hermes"]["target_type"] == "member"
    assert "Tiers" not in changes  # surcharge de membre conservée

    r = apply(env, 102, "role_required", body["token"], roles=[15])
    assert r.status_code == 200 and r.json() == {"applied": 1, "failed": [], "memo_failed": []}
    (written, reason), = g.child1.edits
    assert reason == REASON
    final = ids(g.child1.overwrites)
    assert final[77][0].value == VIEW                      # membre tiers intact
    assert final[1][1].view_channel and final[15][0].view_channel
    assert env.memo[102]["template"] == "role_required" and env.memo[102]["roles"] == [15]
    assert env.memo[102]["applied_by"] == 42


def test_state_change_between_preview_and_apply_is_409(env):
    token = preview(env, 101, "public").json()["token"]
    env.guild.general.overwrites[env.guild.vip] = ow(allow=VIEW)  # quelqu'un modifie le salon
    r = apply(env, 101, "public", token)
    assert r.status_code == 409 and "l'aperçu n'est plus à jour" in r.json()["detail"].lower()
    assert env.guild.general.edits == [] and 101 not in env.memo


def test_token_is_bound_to_the_previewed_template(env):
    token = preview(env, 101, "public").json()["token"]
    assert apply(env, 101, "role_required", token, roles=[15]).status_code == 409
    assert apply(env, 101, "public", token).status_code == 200


def test_switch_role_required_to_public_removes_managed_overwrites_only(env):
    g = env.guild
    token = preview(env, 102, "role_required", roles=[15]).json()["token"]
    apply(env, 102, "role_required", token, roles=[15])
    g.child1.overwrites[g.membre] = ow(allow=VIEW)  # rôle tiers ajouté à la main
    body = preview(env, 102, "public").json()
    removed = {c["target_name"] for c in body["channels"][0]["changes"] if c["action"] == "remove"}
    assert removed == {"@everyone", "VIP"}
    assert apply(env, 102, "public", body["token"]).status_code == 200
    assert set(ids(g.child1.overwrites)) == {77, 10, 500}


def test_category_sync_children_covers_every_channel(env):
    g = env.guild
    body = preview(env, 100, "role_required", roles=[15], sync=True).json()
    assert body["count"] == 3
    assert [c["name"] for c in body["channels"]] == ["Jeux", "minecraft", "vocal-jeux"]
    vocal = next(c for c in body["channels"] if c["type"] == "voice")
    vip = next(c for c in vocal["changes"] if c["target_name"] == "VIP")
    assert "connect" in vip["after"]["allow"]
    # un salon enfant change : le jeton global n'est plus valable
    g.child2.overwrites[g.membre] = ow(allow=VIEW)
    assert apply(env, 100, "role_required", body["token"], roles=[15], sync=True).status_code == 409
    body = preview(env, 100, "role_required", roles=[15], sync=True).json()
    r = apply(env, 100, "role_required", body["token"], roles=[15], sync=True)
    assert r.json() == {"applied": 3, "failed": [], "memo_failed": []}
    assert all(ch.edits for ch in (g.cat, g.child1, g.child2))
    assert set(env.memo) == {100, 102, 103}


def test_category_without_sync_touches_category_only(env):
    body = preview(env, 100, "public").json()
    assert body["count"] == 1
    apply(env, 100, "public", body["token"])
    assert env.guild.child1.edits == [] and set(env.memo) == {100}


def test_sync_children_refused_if_a_child_is_hidden(env):
    env.guild.child2.hidden_from.add(43)
    assert preview(env, 100, "public", actor=43, sync=True).status_code == 403
    assert preview(env, 100, "public", actor=43).status_code == 200


def test_partial_failure_is_reported(env):
    g = env.guild
    g.child2.fail = discord.HTTPException(SimpleNamespace(status=500, reason="boom"), "boom")
    body = preview(env, 100, "public", sync=True).json()
    r = apply(env, 100, "public", body["token"], sync=True)
    assert r.status_code == 200
    assert r.json()["applied"] == 2 and r.json()["failed"][0]["id"] == "103"
    assert 103 not in env.memo


# ── Resynchronisation des salons « Staff » ───────────────────────────────────

def test_staff_resync_after_staff_roles_change(env):
    g = env.guild
    token = preview(env, 104, "staff", actor=999).json()["token"]
    assert apply(env, 104, "staff", token, actor=999).status_code == 200
    assert env.memo[104]["roles"] == [20]
    env.staff_roles[:] = [g.vip]  # staff_roles changé : VIP remplace Modo
    r = env.client.post("/discord/channels/staff-resync/preview", json={"actor_id": "999"})
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 1
    changes = {c["target_name"]: c["action"] for c in body["channels"][0]["changes"]}
    assert changes == {"VIP": "add", "Modo": "remove"}
    r = env.client.post("/discord/channels/staff-resync/apply",
                        json={"actor_id": "999", "actor_name": "Alice", "token": "faux"})
    assert r.status_code == 409
    r = env.client.post("/discord/channels/staff-resync/apply",
                        json={"actor_id": "999", "actor_name": "Alice", "token": body["token"]})
    assert r.json() == {"applied": 1, "failed": [], "memo_failed": []}
    assert env.memo[104]["roles"] == [15] and 20 not in ids(g.staff.overwrites)


def test_staff_template_without_staff_roles_is_422(env):
    env.staff_roles.clear()
    assert preview(env, 101, "staff").status_code == 422
    assert env.client.post("/discord/channels/staff-resync/preview",
                           json={"actor_id": "42"}).status_code == 422


# ── Correction tour 1 : R2, R3, acteur obligatoire ───────────────────────────

def test_cannot_add_or_update_overwrite_of_role_above_actor(env):
    # staff_roles contient Admin (8) : Alice (Modo, 4) ne peut pas l'ajouter ; le propriétaire le peut.
    env.staff_roles[:] = [env.guild.admin]
    r = preview(env, 101, "staff")
    assert r.status_code == 403 and "Impossible de modifier la surcharge du rôle" in r.json()["detail"]
    assert "Admin" in r.json()["detail"]
    token = preview(env, 101, "staff", actor=999).json()["token"]
    assert apply(env, 101, "staff", token, actor=999).status_code == 200
    # modification (update) d'une surcharge existante du rôle au-dessus : refusée aussi
    env.guild.general.overwrites[env.guild.admin] = ow(allow=VIEW)
    r = preview(env, 101, "staff")
    assert r.status_code == 403 and "Impossible de modifier" in r.json()["detail"]


def test_memo_failure_is_isolated_logged_and_reported(env, monkeypatch, caplog):
    g = env.guild
    real = channels_api.save_template

    async def flaky(cid, template, roles, applied_by):
        if cid == 102:
            raise RuntimeError("base indisponible")
        await real(cid, template, roles, applied_by)

    monkeypatch.setattr(channels_api, "save_template", flaky)
    body = preview(env, 100, "public", sync=True).json()
    with caplog.at_level("ERROR"):
        r = apply(env, 100, "public", body["token"], sync=True)
    assert r.status_code == 200
    assert r.json() == {"applied": 3, "failed": [], "memo_failed": ["102"]}
    assert g.child1.edits and g.child2.edits           # la boucle a continué
    assert set(env.memo) == {100, 103}
    assert any("102" in rec.getMessage() for rec in caplog.records)


def test_memo_failed_is_empty_list_when_all_good(env):
    token = preview(env, 101, "public").json()["token"]
    assert apply(env, 101, "public", token).json()["memo_failed"] == []


def test_patch_and_delete_require_actor_id(env):
    c = env.client
    assert c.patch("/discord/channels/101", json={"name": "x", "actor_name": "Alice"}).status_code == 422
    assert c.request("DELETE", "/discord/channels/105", json={"actor_name": "Alice"}).status_code == 422
    assert env.guild.general.edits == [] and env.guild.empty_cat in env.guild.channels


def test_delete_refused_when_actor_does_not_see_channel(env):
    r = env.client.request("DELETE", "/discord/channels/104", json={"actor_id": "43", "actor_name": "Bob"})
    assert r.status_code == 403 and env.guild.staff in env.guild.channels
    env.guild.staff.hidden_from.add(999)
    r = env.client.request("DELETE", "/discord/channels/104", json={"actor_id": "999", "actor_name": "P"})
    assert r.status_code == 200  # propriétaire exempté


# ── Aucun nom de salon invisible dans les réponses ───────────────────────────

def test_hidden_channel_name_never_in_403_bodies(env):
    c = env.client
    r = c.patch("/discord/channels/104", json={"name": "x", "actor_id": "43", "actor_name": "Bob"})
    assert r.status_code == 403 and "staff" not in r.text
    r = c.request("DELETE", "/discord/channels/104", json={"actor_id": "43", "actor_name": "Bob"})
    assert r.status_code == 403 and "staff" not in r.text
    assert preview(env, 104, "public", actor=43).status_code == 403
    assert "staff" not in preview(env, 104, "public", actor=43).text


def test_sync_with_hidden_child_refused_without_name(env):
    env.guild.child2.hidden_from.add(43)
    r = preview(env, 100, "public", actor=43, sync=True)
    assert r.status_code == 403 and "vocal-jeux" not in r.text
    r = apply(env, 100, "public", "nimporte", actor=43, sync=True)
    assert r.status_code == 403 and "vocal-jeux" not in r.text


def test_staff_resync_hidden_staff_channel_refused_without_name(env):
    token = preview(env, 104, "staff", actor=999).json()["token"]
    assert apply(env, 104, "staff", token, actor=999).status_code == 200
    r = env.client.post("/discord/channels/staff-resync/preview", json={"actor_id": "43"})
    assert r.status_code == 403 and "staff" not in r.text.replace("Vous ne voyez pas", "")
    r = env.client.post("/discord/channels/staff-resync/apply",
                        json={"actor_id": "43", "actor_name": "Bob", "token": "x"})
    assert r.status_code == 403 and "staff" not in r.text.replace("Vous ne voyez pas", "")


# ── Création / déplacement vers une catégorie que l'acteur ne voit pas (I1) ──

def _create(env, actor=42, parent="100", **extra):
    return env.client.post("/discord/channels", json={
        "name": "nouveau", "type": "text", "parent_id": parent, "actor_id": str(actor),
        "actor_name": "Alice", **extra})


def test_create_requires_actor_id(env):
    r = env.client.post("/discord/channels", json={"name": "x", "type": "text", "actor_name": "Alice"})
    assert r.status_code == 422 and env.guild.created == []


def test_create_in_hidden_category_is_403_without_name(env):
    env.guild.cat.hidden_from.add(42)
    r = _create(env)
    assert r.status_code == 403 and env.guild.created == []
    assert "Jeux" not in r.text
    r = _create(env, type="category", parent=None)  # sans parent : aucun contrôle de catégorie
    assert r.status_code == 200


def test_create_in_hidden_category_owner_is_exempt(env):
    env.guild.cat.hidden_from.add(999)
    assert _create(env, actor=999).status_code == 200 and len(env.guild.created) == 1


def test_create_with_absent_actor_is_403(env):
    assert _create(env, actor=12345).status_code == 403 and env.guild.created == []


def test_move_into_hidden_category_is_403_without_name(env):
    env.guild.cat.hidden_from.add(42)
    r = env.client.patch("/discord/channels/101", json={"parent_id": "100", "actor_id": "42",
                                                        "actor_name": "Alice"})
    assert r.status_code == 403 and env.guild.general.edits == [] and "Jeux" not in r.text


def test_move_into_hidden_category_owner_is_exempt(env):
    env.guild.cat.hidden_from.add(999)
    r = env.client.patch("/discord/channels/101", json={"parent_id": "100", "actor_id": "999",
                                                        "actor_name": "P"})
    assert r.status_code == 200 and env.guild.general.category_id == 100


def test_leaving_a_category_needs_no_destination_check(env):
    env.guild.cat.hidden_from.add(42)
    r = env.client.patch("/discord/channels/102", json={"parent_id": None, "actor_id": "42",
                                                        "actor_name": "Alice"})
    assert r.status_code == 200 and env.guild.child1.category_id is None


# ── delete_channel : échec du mémo isolé (M5) ────────────────────────────────

def test_delete_memo_failure_is_isolated_logged_and_reported(env, monkeypatch, caplog):
    async def boom(cid):
        raise RuntimeError("base indisponible")

    monkeypatch.setattr(channels_api, "delete_template", boom)
    with caplog.at_level("ERROR"):
        r = env.client.request("DELETE", "/discord/channels/105",
                               json={"actor_id": "42", "actor_name": "Alice"})
    assert r.status_code == 200 and r.json() == {"ok": True, "memo_failed": ["105"]}
    assert env.guild.empty_cat not in env.guild.channels
    assert any("105" in rec.getMessage() for rec in caplog.records)


def test_delete_without_memo_failure_has_empty_memo_failed(env):
    r = env.client.request("DELETE", "/discord/channels/105", json={"actor_id": "42", "actor_name": "Alice"})
    assert r.json() == {"ok": True, "memo_failed": []}
