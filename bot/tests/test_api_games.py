"""API interne : jeux (étape 4, tâche 4) — routes /games/* branchées sur le vrai GameManager.

Le faux Discord et la fausse base viennent de ``test_game_manager`` : ces tests vérifient le
contrat HTTP (forme des réponses, traduction des erreurs Discord en français) au-dessus du
comportement du cog, déjà couvert là-bas.
"""
import asyncio
import os
import sys
import types
from types import SimpleNamespace as N

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

from tests.test_game_manager import FakeRole, FakeTree, row  # noqa: E402,F401
from tests.test_game_manager import make  # noqa: E402,F401  (fixture)

TOKEN = "jeton-de-test"


@pytest.fixture
def env(make, monkeypatch):
    monkeypatch.setattr(api, "BOT_API_TOKEN", TOKEN)

    def factory(**kwargs):
        e = make(**kwargs)
        monkeypatch.setattr(api, "_bot", e.bot)
        client = TestClient(api.app)
        client.__enter__()  # la boucle survit entre requêtes (synchronisation regroupée)
        client.headers["Authorization"] = f"Bearer {TOKEN}"
        e.http = client
        e.portal = client.portal
        created.append(client)
        # Démarrage du cog dans la boucle du client (verrou, tâches de synchronisation).
        client.portal.call(e.gm.cog_load)
        return e

    created: list = []
    yield factory
    for client in created:
        client.__exit__(None, None, None)


def _discord_error(cls, status, text):
    return cls(N(status=status, reason=text), text)


# ── Jeton ────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("method,url", [
    ("post", "/games/reload"), ("get", "/games/status"), ("get", "/games/taken"),
    ("post", "/games/resync-permissions"), ("post", "/games/lol/provision"),
    ("post", "/games/lol/archive"), ("post", "/games/lol/unarchive"),
])
def test_routes_jeux_exigent_le_jeton(env, method, url):
    e = env()
    r = getattr(e.http, method)(url, headers={"Authorization": "Bearer faux"})
    assert r.status_code == 401


def test_cog_absent_503(env):
    e = env()
    del e.bot.cogs["GameManager"]
    r = e.http.get("/games/status")
    assert r.status_code == 503 and r.json()["detail"] == "Gestion des jeux non chargée"


# ── Statut et noms pris ──────────────────────────────────────────────────────

def test_statut_des_jeux_et_nombre_de_forums(env):
    e = env()
    body = e.http.get("/games/status").json()
    assert body["loaded"] is True
    assert body["games"]["dbd"] == {"role": "ok", "forum": "ok", "command": "ok"}
    assert body["games"]["war-dogs"] == {"role": "missing", "forum": "missing", "command": "none"}
    assert body["resync_forums"] == 6  # War Dogs non provisionné : pas de forum


def test_statut_forum_supprime_a_la_main(env):
    e = env()
    e.guild.forums = [f for f in e.guild.forums if f.name != "lol"]
    body = e.http.get("/games/status").json()
    assert body["games"]["lol"]["forum"] == "missing"
    assert body["resync_forums"] == 5


def test_noms_pris_incluent_les_commandes_du_bot_et_les_autres_jeux(env):
    e = env(tree=FakeTree(global_names=("rang", "blague")))
    taken = e.http.get("/games/taken", params={"exclude": "lol"}).json()
    assert {"rang", "blague", "dbd", "minecraft"} <= set(taken["commands"])
    assert "lol" not in taken["commands"]  # le jeu lui-même peut garder son nom
    assert {"⭐", "📺", "🎭", "🔪"} <= set(taken["emojis"]) and "⚔️" not in taken["emojis"]
    creation = e.http.get("/games/taken").json()
    assert "lol" in creation["commands"] and "⚔️" in creation["emojis"]


# ── Rechargement ─────────────────────────────────────────────────────────────

def test_reload_suit_la_base(env):
    e = env()
    e.db.rows["apex"] = row("apex", "Apex", position=9, emoji="🎯", command="apex", provisioned=True)
    assert e.http.post("/games/reload").json() == {"ok": True}
    assert "apex" in e.tree.guild_names()
    assert e.http.get("/games/status").json()["games"]["apex"]["command"] == "ok"


# ── Provisionnement ──────────────────────────────────────────────────────────

def test_provision_cree_role_et_forum(env):
    e = env()
    e.db.rows["war-dogs"].update(emoji="🐺", command_name="wardogs")
    r = e.http.post("/games/war-dogs/provision")
    assert r.status_code == 200
    body = r.json()
    role, forum = e.guild.created_roles[0], e.guild.created_forums[0]
    assert body == {"role_id": str(role.id), "forum_id": str(forum.id), "command": "wardogs",
                    "created": ["role", "forum"],
                    "status": {"role": "ok", "forum": "ok", "command": "ok"}}
    assert e.db.rows["war-dogs"]["provisioned"] is True


def test_provision_homonyme_409_sauf_reutilisation_demandee(env):
    e = env()
    e.guild.roles.append(FakeRole(300, "war dogs"))
    r = e.http.post("/games/war-dogs/provision")
    assert r.status_code == 409
    assert r.json()["detail"] == "Un rôle de ce nom existe déjà : demandez à un admin de le rattacher"
    assert e.guild.created_roles == [] and e.db.rows["war-dogs"]["provisioned"] is False
    r = e.http.post("/games/war-dogs/provision", json={"reuse_existing": True})
    assert r.status_code == 200 and r.json()["role_id"] == "300"


def test_provision_role_a_permissions_409(env):
    e = env()
    e.guild.roles.append(FakeRole(300, "War Dogs", permissions=discord.Permissions(administrator=True).value))
    r = e.http.post("/games/war-dogs/provision", json={"reuse_existing": True})
    assert r.status_code == 409 and "donne des permissions" in r.json()["detail"]


def test_provision_deuxieme_clic_ne_cree_rien(env):
    e = env()
    e.db.rows["war-dogs"].update(emoji="🐺", command_name="wardogs")
    e.http.post("/games/war-dogs/provision")
    body = e.http.post("/games/war-dogs/provision").json()
    assert body["created"] == [] and len(e.guild.created_roles) == 1


def test_provision_jeu_inconnu_404(env):
    e = env()
    r = e.http.post("/games/nope/provision")
    assert r.status_code == 404 and r.json()["detail"] == "Jeu inconnu"


def test_provision_cle_invalide_422(env):
    e = env()
    assert e.http.post("/games/Bad_Key/provision").status_code == 422


@pytest.mark.parametrize("error,status,detail", [
    (_discord_error(discord.Forbidden, 403, "Missing Permissions"), 403,
     "Permission refusée — le bot n'a pas les droits nécessaires (Gérer les rôles, Gérer les salons)"),
    (_discord_error(discord.NotFound, 404, "Unknown Channel"), 404, "Rôle ou salon Discord introuvable"),
    (_discord_error(discord.HTTPException, 500, "boom"), 502, "Erreur Discord : boom"),
])
def test_provision_erreurs_discord_traduites(env, error, status, detail):
    e = env()

    async def refused(*args, **kwargs):
        raise error

    e.guild.create_forum_channel = refused
    r = e.http.post("/games/war-dogs/provision")
    assert r.status_code == status and r.json()["detail"] == detail
    # Le rôle créé avant l'échec est gardé : un nouveau clic ne le recréera pas.
    assert e.db.rows["war-dogs"]["discord_role_id"] == e.guild.created_roles[0].id


def test_provision_serveur_introuvable_503(env):
    e = env()
    e.bot.guild = None
    r = e.http.post("/games/war-dogs/provision")
    assert r.status_code == 503 and r.json()["detail"] == "Serveur Discord introuvable"


# ── Archivage ────────────────────────────────────────────────────────────────

def test_archive_puis_unarchive(env):
    e = env()
    r = e.http.post("/games/warframe/archive")
    assert r.status_code == 200
    assert r.json() == {"status": {"role": "ok", "forum": "ok", "command": "none"}}
    assert e.db.rows["warframe"]["archived"] is True and "warframe" not in e.tree.guild_names()
    r = e.http.post("/games/warframe/unarchive")
    assert r.json() == {"status": {"role": "ok", "forum": "ok", "command": "ok"}}
    assert "warframe" in e.tree.guild_names()


def test_archive_refuse_par_discord_403_etat_coherent(env):
    e = env()
    forum = next(f for f in e.guild.forums if f.name == "warframe")

    async def refused(*args, **kwargs):
        raise _discord_error(discord.Forbidden, 403, "Missing Permissions")

    forum.set_permissions = refused
    r = e.http.post("/games/warframe/archive")
    assert r.status_code == 403 and r.json()["detail"].startswith("Permission refusée")
    assert e.db.rows["warframe"]["archived"] is True and "warframe" not in e.tree.guild_names()


def test_archive_inconnu_404(env):
    e = env()
    assert e.http.post("/games/nope/archive").status_code == 404
    assert e.http.post("/games/nope/unarchive").status_code == 404


# ── Resynchronisation ────────────────────────────────────────────────────────

def test_resync_permissions_compte_les_forums(env):
    e = env()
    assert e.http.post("/games/resync-permissions").json() == {"forums": 6}
    assert all(len(f.edits) == 1 for f in e.guild.forums)


def test_resync_permissions_refus_discord_traduit(env):
    e = env()

    async def refused(*args, **kwargs):
        raise _discord_error(discord.Forbidden, 403, "Missing Permissions")

    e.guild.forums[0].edit = refused
    r = e.http.post("/games/resync-permissions")
    assert r.status_code == 403


def test_synchronisation_regroupee_via_l_api(env):
    """Cinq jeux ajoutés d'affilée par le site → une seule synchronisation des commandes."""
    e = env()
    for i in range(5):
        key = f"jeu{i}"
        e.db.rows[key] = row(key, f"Jeu {i}", position=10 + i, emoji=chr(0x1F600 + i), command=key)
        assert e.http.post(f"/games/{key}/provision").status_code == 200
    e.portal.call(asyncio.sleep, 0.2)
    assert e.tree.syncs == [42]
