"""API interne : permissions des rôles, catalogue des commandes, rechargement des listes (étape 6, tâche 2)."""
import os
import sys
import types
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import discord  # noqa: E402
import pytest  # noqa: E402
from discord import app_commands  # noqa: E402

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

from utils import command_permissions as cp  # noqa: E402
from utils.decorators import administration_only  # noqa: E402

TOKEN = "jeton-de-test"
REASON = "via le site par Alice"
P = discord.Permissions
ADMIN = P(administrator=True).value
BAN = P(ban_members=True).value
KICK = P(kick_members=True).value
SEND = P(send_messages=True).value
UNKNOWN_BIT = 1 << 62  # bit hors catalogue (permission future de Discord)


class FakeRole:
    def __init__(self, rid, name, position, perms=0, *, managed=False, default=False):
        self.id, self.name, self.position = rid, name, position
        self.permissions = P(perms)
        self.managed, self._default = managed, default
        self.edits = []
        self.fail = None

    def is_default(self):
        return self._default

    async def edit(self, *, permissions, reason):
        if self.fail:
            raise self.fail
        self.edits.append((permissions.value, reason))
        self.permissions = permissions
        return self


class FakeMember:
    def __init__(self, mid, top_role, perms):
        self.id, self.top_role = mid, top_role
        self.guild_permissions = P(perms)


class FakeGuild:
    owner_id = 999

    def __init__(self):
        self.everyone = FakeRole(1, "@everyone", 0, SEND, default=True)
        self.membre = FakeRole(10, "Membre", 1, SEND)
        self.vip = FakeRole(15, "VIP", 2, SEND | KICK)
        self.integration = FakeRole(20, "Bot Musique", 3, managed=True)
        self.modo = FakeRole(25, "Modo", 4, SEND | KICK)
        self.bot_role = FakeRole(30, "Hermes", 6, managed=True)
        self.admin = FakeRole(40, "Admin", 8, ADMIN)
        self.roles = [self.everyone, self.membre, self.vip, self.integration, self.modo,
                      self.bot_role, self.admin]
        self.me = SimpleNamespace(top_role=self.bot_role)
        self._members = {
            # modérateur : expulser oui, bannir non
            7: FakeMember(7, self.modo, SEND | KICK),
            8: FakeMember(8, self.admin, ADMIN),
            999: FakeMember(999, self.admin, ADMIN),
        }

    def get_member(self, user_id):
        return self._members.get(user_id)

    async def fetch_member(self, user_id):
        raise discord.NotFound(SimpleNamespace(status=404, reason="Not Found"), "Unknown Member")

    def get_role(self, role_id):
        return next((r for r in self.roles if r.id == role_id), None)


class FakeTree:
    def __init__(self, global_cmds=(), guild_cmds=()):
        self.global_cmds, self.guild_cmds = list(global_cmds), list(guild_cmds)

    def get_commands(self, guild=None):
        return self.guild_cmds if guild is not None else self.global_cmds


@pytest.fixture
def env(monkeypatch):
    guild = FakeGuild()
    bot = SimpleNamespace(tree=FakeTree())
    monkeypatch.setattr(api, "BOT_API_TOKEN", TOKEN)
    monkeypatch.setattr(api, "_get_guild", lambda: guild)
    monkeypatch.setattr(api, "_bot", bot)
    with TestClient(api.app) as client:
        client.headers["Authorization"] = f"Bearer {TOKEN}"
        yield SimpleNamespace(http=client, guild=guild, bot=bot)


def patch(http, role_id, actor_id, permissions, **extra):
    return http.patch(f"/discord/roles/{role_id}/permissions",
                      json={"actor_id": str(actor_id), "actor_name": "Alice",
                            "permissions": permissions, **extra})


# ── Lecture ──────────────────────────────────────────────────────────────────

def test_lecture_roles_acteur_et_bot(env):
    body = env.http.get("/discord/roles/permissions", params={"actor_id": 7}).json()
    roles = {r["id"]: r for r in body["roles"]}
    assert [r["name"] for r in body["roles"]][0] == "Admin"  # du plus haut au plus bas
    assert roles["15"] == {"id": "15", "name": "VIP", "position": 2, "managed": False,
                           "is_default": False, "permissions": SEND | KICK}
    assert roles["1"]["is_default"] is True
    assert roles["20"]["managed"] is True
    assert body["actor"] == {"permissions": SEND | KICK, "top_position": 4, "is_owner": False}
    assert body["bot"] == {"top_position": 6}


def test_lecture_acteur_hors_serveur_403(env):
    assert env.http.get("/discord/roles/permissions", params={"actor_id": 12345}).status_code == 403


# ── Anti-escalade ────────────────────────────────────────────────────────────

def test_activer_une_permission_non_possedee_403(env):
    r = patch(env.http, 15, 7, SEND | KICK | BAN)
    assert r.status_code == 403
    assert env.guild.vip.edits == []


def test_retirer_une_permission_non_possedee_403(env):
    env.guild.vip.permissions = P(SEND | ADMIN)
    r = patch(env.http, 15, 7, SEND)
    assert r.status_code == 403
    assert env.guild.vip.edits == []


def test_permission_possedee_modifiable_avec_raison_d_audit(env):
    r = patch(env.http, 15, 7, SEND)
    assert r.status_code == 200, r.text
    assert env.guild.vip.edits == [(SEND, REASON)]
    body = r.json()
    assert body["before"] == SEND | KICK and body["after"] == SEND
    assert body["role"]["permissions"] == SEND


def test_role_au_niveau_ou_au_dessus_de_l_acteur_403(env):
    assert patch(env.http, 25, 7, SEND).status_code == 403  # son propre rôle le plus haut
    assert patch(env.http, 40, 8, ADMIN).status_code == 403


def test_role_au_dessus_du_bot_refuse_meme_au_proprietaire(env):
    assert patch(env.http, 40, 999, ADMIN).status_code == 403


def test_role_gere_par_une_integration_403(env):
    assert patch(env.http, 20, 999, SEND).status_code == 403


def test_everyone_reserve_au_proprietaire(env):
    assert patch(env.http, 1, 8, 0).status_code == 403
    r = patch(env.http, 1, 999, 0)
    assert r.status_code == 200, r.text
    assert env.guild.everyone.edits == [(0, REASON)]


def test_administrateur_activable_par_le_proprietaire_seul_et_confirme(env):
    # un acteur administrateur non propriétaire : refusé, même confirmé
    assert patch(env.http, 15, 8, SEND | ADMIN, confirm_administrator=True).status_code == 403
    # propriétaire sans confirmation : refusé
    r = patch(env.http, 15, 999, SEND | ADMIN)
    assert r.status_code == 422 and "confirmation" in r.json()["detail"]
    assert env.guild.vip.edits == []
    r = patch(env.http, 15, 999, SEND | ADMIN, confirm_administrator=True)
    assert r.status_code == 200
    assert env.guild.vip.edits == [(SEND | ADMIN, REASON)]


def test_acteur_administrateur_modifie_tout_sauf_administrateur(env):
    r = patch(env.http, 15, 8, SEND | BAN)
    assert r.status_code == 200
    assert env.guild.vip.edits == [(SEND | BAN, REASON)]


def test_permission_inconnue_422(env):
    assert patch(env.http, 15, 999, SEND | UNKNOWN_BIT).status_code == 422


def test_bits_hors_catalogue_deja_poses_conserves(env):
    env.guild.vip.permissions = P(SEND | KICK | UNKNOWN_BIT)
    r = patch(env.http, 15, 7, SEND)
    assert r.status_code == 200
    assert env.guild.vip.edits == [(SEND | UNKNOWN_BIT, REASON)]


def test_sans_changement_aucun_appel_discord(env):
    assert patch(env.http, 15, 7, SEND | KICK).status_code == 200
    assert env.guild.vip.edits == []


def test_role_introuvable_404_et_erreur_discord_traduite(env):
    assert patch(env.http, 4242, 999, SEND).status_code == 404
    env.guild.vip.fail = discord.Forbidden(SimpleNamespace(status=403, reason="Forbidden"), "Missing")
    r = patch(env.http, 15, 999, SEND)
    assert r.status_code == 403 and "Gérer les rôles" in r.json()["detail"]


# ── Catalogue des commandes ──────────────────────────────────────────────────

def _cmd(name, *, admin=False, native=False):
    async def body(interaction):
        pass

    callback = administration_only()(body) if admin else body
    if native:
        callback = app_commands.checks.has_permissions(manage_channels=True)(callback)
    return app_commands.Command(name=name, description=f"desc {name}", callback=callback)


def test_catalogue_des_commandes(env):
    group = app_commands.Group(name="ticket", description="Tickets")

    @group.command(name="close", description="Fermer")
    async def close(interaction):
        pass

    @group.command(name="list", description="Lister")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def list_(interaction):
        pass

    env.bot.tree = FakeTree([_cmd("kick", admin=True), _cmd("blague"), group],
                            [_cmd("lol"), _cmd("blague")])
    body = env.http.get("/commands/catalog").json()
    assert body["commands"] == [
        {"name": "blague", "description": "desc blague", "admin_only": False, "native_protected": False},
        {"name": "kick", "description": "desc kick", "admin_only": True, "native_protected": False},
        {"name": "lol", "description": "desc lol", "admin_only": False, "native_protected": False},
        {"name": "ticket", "description": "Tickets", "admin_only": False, "native_protected": True},
    ]


# ── Rechargement des listes ─────────────────────────────────────────────────

class FakeDb:
    def __init__(self, rows=(), fail=False):
        self.rows, self.fail = list(rows), fail

    async def fetch(self, query, *args):
        if self.fail:
            raise ConnectionError("base indisponible")
        return self.rows


def test_rechargement_et_echec_garde_l_ancienne_liste(env, monkeypatch):
    db = FakeDb([{"command_name": "blague", "role_id": 15}, {"command_name": "blague", "role_id": 777}])
    monkeypatch.setattr(cp, "db_manager", db)
    monkeypatch.setattr(cp, "_allowed", {})
    monkeypatch.setattr(cp, "_loaded", False)
    r = env.http.post("/command-permissions/reload")
    assert r.json() == {"ok": True, "restricted": 1}
    assert cp.allowed_roles("blague") == {15, 777}
    db.fail = True
    r = env.http.post("/command-permissions/reload")
    assert r.status_code == 503
    assert cp.allowed_roles("blague") == {15, 777}


def test_routes_protegees_par_jeton(env):
    env.http.headers["Authorization"] = "Bearer mauvais"
    assert env.http.get("/commands/catalog").status_code == 401
    assert env.http.post("/command-permissions/reload").status_code == 401
    assert env.http.get("/discord/roles/permissions", params={"actor_id": 7}).status_code == 401
    assert patch(env.http, 15, 999, SEND).status_code == 401
