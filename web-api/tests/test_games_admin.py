"""Administration des jeux (étape 4, tâche 4) : création, provisionnement, archivage, permissions.

Droits ``games.manage`` (resynchronisation réservée admin), validations 422 (nom de commande,
émoji), relais des erreurs du bot, journal ``audit_events`` (kind ``game``).
"""
import json

import asyncpg
import httpx
import pytest
from fastapi import HTTPException

import bot_client
from routes import admin, content

LOL = {"key": "lol", "name": "League of Legends"}
OTHERS = [  # autres jeux en base (hors jeu modifié)
    {"key": "dbd", "emoji": "🔪", "command_name": "dbd"},
    {"key": "warframe", "emoji": "🚀", "command_name": "warframe"},
    {"key": "war-dogs", "emoji": None, "command_name": None},
]
BOT_COMMANDS = ["rang", "blague", "dbd", "warframe", "lol"]
NEW = {"key": "apex", "name": "Apex Legends", "color": "#AA0000", "emoji": "🎯", "command_name": "apex"}


@pytest.fixture(autouse=True)
def _fresh():
    bot_client.clear_cache()
    yield
    bot_client.clear_cache()


@pytest.fixture
def bot(monkeypatch):
    """Bot factice : ``responses[(méthode, chemin)]`` = valeur ou exception ; appels dans ``calls``."""
    state = {"calls": [], "responses": {
        ("post", "/games/reload"): {"ok": True},
        ("get", "/games/status"): {"loaded": True, "resync_forums": 6, "games": {
            "lol": {"role": "ok", "forum": "ok", "command": "ok"},
            "war-dogs": {"role": "missing", "forum": "missing", "command": "none"}}},
        ("post", "/games/resync-permissions"): {"forums": 6},
        ("post", "/games/lol/archive"): {"status": {"role": "ok", "forum": "ok", "command": "none"}},
        ("post", "/games/lol/unarchive"): {"status": {"role": "ok", "forum": "ok", "command": "ok"}},
        ("post", "/games/lol/provision"): {"role_id": "11", "forum_id": "22", "command": "lol",
                                           "created": ["forum"],
                                           "status": {"role": "ok", "forum": "ok", "command": "ok"}},
    }}

    async def fake_bot(method, path, *, timeout=10, **kwargs):
        state["calls"].append((method, path, timeout, kwargs))
        if path == "/games/taken" and ("get", path) not in state["responses"]:
            exclude = kwargs.get("params", {}).get("exclude")
            return {"commands": [c for c in BOT_COMMANDS if c != exclude], "emojis": ["⭐", "📺", "🎭"]}
        result = state["responses"].get((method, path))
        if result is None:
            raise AssertionError(f"appel bot inattendu : {method} {path}")
        if isinstance(result, Exception):
            raise result
        return result

    async def fake_bot_get(path, timeout=1.5):
        try:
            return await fake_bot("get", path, timeout=timeout)
        except Exception:
            return None

    monkeypatch.setattr(admin, "_bot", fake_bot)
    monkeypatch.setattr(content, "bot_get", fake_bot_get)
    return state


@pytest.fixture
def games_db(fake_db):
    fake_db.on("SELECT key, name FROM site_games", lambda sql, key: LOL if key == "lol" else None)
    fake_db.on("SELECT key, emoji, command_name FROM site_games",
               lambda sql, key: [r for r in OTHERS + [{"key": "lol", "emoji": "⚔️", "command_name": "lol"}]
                                 if r["key"] != key])
    return fake_db


@pytest.fixture
def manager(session_with):
    return session_with({"games.manage"})


def _audit(fake_db):
    """Lignes écrites dans ``audit_events`` : dict kind/action/source/target_name/details/success."""
    rows = []
    for method, sql, args in fake_db.calls:
        if method == "execute" and "INSERT INTO audit_events" in sql:
            kind, action, source, _actor, _name, _tid, target_name, details, success = args
            rows.append({"kind": kind, "action": action, "source": source, "target_name": target_name,
                         "details": json.loads(details), "success": success})
    return rows


def _game_writes(fake_db):
    return [(sql, args) for m, sql, args in fake_db.calls if m == "execute" and "site_games" in sql]


# ── Droits ───────────────────────────────────────────────────────────────────

CALLS = [
    ("get", "/admin/games", None),
    ("post", "/admin/games", NEW),
    ("put", "/admin/games/lol", {"emoji": "🎯"}),
    ("delete", "/admin/games/lol", None),
    ("post", "/admin/games/lol/reactivate", None),
    ("post", "/admin/games/lol/provision", None),
    ("get", "/admin/games/resync-permissions", None),
    ("post", "/admin/games/resync-permissions", {"confirm_forums": 6}),
]


@pytest.mark.parametrize("method,url,body", CALLS)
def test_sans_games_manage_403(client, games_db, bot, session_with, method, url, body):
    kwargs = {"json": body} if body is not None else {}
    assert client.request(method.upper(), url, **kwargs).status_code == 401  # sans session
    session_with({"settings.manage", "roles.manage"})
    assert client.request(method.upper(), url, **kwargs).status_code == 403
    assert not _game_writes(games_db) and not [c for c in bot["calls"] if c[0] == "post"]


@pytest.mark.parametrize("method,url,body", [c for c in CALLS if "resync" not in c[1]])
def test_games_manage_suffit(client, games_db, bot, manager, method, url, body):
    kwargs = {"json": body} if body is not None else {}
    assert client.request(method.upper(), url, **kwargs).status_code in (200, 201)


@pytest.mark.parametrize("method,body", [("get", None), ("post", {"confirm_forums": 6})])
def test_resync_reserve_aux_admins(client, games_db, bot, session_with, method, body):
    session_with({"games.manage", "settings.manage"})
    kwargs = {"json": body} if body is not None else {}
    r = client.request(method.upper(), "/admin/games/resync-permissions", **kwargs)
    assert r.status_code == 403 and r.json()["detail"].startswith("Réservé aux administrateurs")
    assert ("post", "/games/resync-permissions") not in [(c[0], c[1]) for c in bot["calls"]]


# ── Liste avec statut ────────────────────────────────────────────────────────

ROWS = [
    {"key": "war-dogs", "name": "War Dogs", "color": "#A12D2F", "image": None, "tagline": None,
     "discord_role_id": None, "forum_channel_id": None, "position": 1, "active": True, "emoji": None,
     "command_name": None, "lfg_cooldown": 3600, "provisioned": False, "archived": False},
    {"key": "lol", "name": "League of Legends", "color": "#F5A623", "image": None, "tagline": None,
     "discord_role_id": 11, "forum_channel_id": 22, "position": 3, "active": True, "emoji": "⚔️",
     "command_name": "lol", "lfg_cooldown": 3600, "provisioned": True, "archived": False},
    {"key": "apex", "name": "Apex", "color": "#AA0000", "image": None, "tagline": None,
     "discord_role_id": None, "forum_channel_id": None, "position": 9, "active": True, "emoji": "🎯",
     "command_name": "apex", "lfg_cooldown": 600, "provisioned": False, "archived": False},
]


def test_liste_inclut_le_statut_discord(client, fake_db, bot, manager):
    fake_db.on("FROM site_games ORDER BY", ROWS)
    body = client.get("/admin/games").json()
    assert body["bot_reachable"] is True
    wd, lol, apex = body["games"]
    assert wd["provisioned"] is False and wd["status"] == {"role": "missing", "forum": "missing",
                                                           "command": "none"}
    assert lol["emoji"] == "⚔️" and lol["command_name"] == "lol" and lol["archived"] is False
    assert lol["status"] == {"role": "ok", "forum": "ok", "command": "ok"}
    assert apex["lfg_cooldown"] == 600 and apex["status"] is None  # inconnu du bot


def test_liste_bot_injoignable(client, fake_db, bot, manager):
    fake_db.on("FROM site_games ORDER BY", ROWS)
    bot["responses"][("get", "/games/status")] = HTTPException(503, "Bot not ready")
    body = client.get("/admin/games").json()
    assert body["bot_reachable"] is False and all(g["status"] is None for g in body["games"])


# ── Création ─────────────────────────────────────────────────────────────────

def test_creation_non_provisionnee_journalisee_et_bot_recharge(client, games_db, bot, manager):
    r = client.post("/admin/games", json={**NEW, "tagline": "Saute, glisse, tire."})
    assert r.status_code == 201 and r.json() == {"ok": True, "key": "apex", "bot_reloaded": True}
    sql, args = _game_writes(games_db)[0]
    assert "INSERT INTO site_games" in sql and "FALSE, FALSE" in sql  # ni provisionné ni archivé
    assert args[0] == "apex" and args[8:] == ("🎯", "apex", 3600)
    assert ("post", "/games/reload") in [(c[0], c[1]) for c in bot["calls"]]
    assert _audit(games_db) == [{"kind": "game", "action": "game_create", "source": "site",
                                 "target_name": "Apex Legends", "success": True,
                                 "details": {"key": "apex", "name": "Apex Legends", "emoji": "🎯",
                                             "command_name": "apex"}}]


def test_creation_bot_muet_au_rechargement(client, games_db, bot, manager):
    bot["responses"][("post", "/games/reload")] = HTTPException(503, "Gestion des jeux non chargée")
    r = client.post("/admin/games", json=NEW)
    assert r.status_code == 201 and r.json()["bot_reloaded"] is False


@pytest.mark.parametrize("field", ["emoji", "command_name", "name", "color"])
def test_creation_champ_requis(client, games_db, bot, manager, field):
    body = {k: v for k, v in NEW.items() if k != field}
    r = client.post("/admin/games", json=body)
    assert r.status_code == 422 and field in r.json()["detail"]
    assert not _game_writes(games_db)


@pytest.mark.parametrize("command", ["rang", "blague"])
def test_nom_egal_a_une_commande_du_bot_422(client, games_db, bot, manager, command):
    r = client.post("/admin/games", json={**NEW, "command_name": command})
    assert r.status_code == 422 and r.json()["detail"] == f"La commande /{command} existe déjà."
    assert not _game_writes(games_db)


def test_nom_deja_pris_par_un_autre_jeu_en_base_422(client, games_db, bot, manager):
    """Même si le bot ne le connaît pas encore (jeu créé, non rechargé) : la base fait foi."""
    global BOT_COMMANDS
    saved, BOT_COMMANDS = BOT_COMMANDS, ["rang"]
    try:
        r = client.post("/admin/games", json={**NEW, "command_name": "warframe"})
    finally:
        BOT_COMMANDS = saved
    assert r.status_code == 422 and r.json()["detail"] == "La commande /warframe existe déjà."


@pytest.mark.parametrize("command", ["Apex", "apex legends", "a" * 33, "", "apex\n", "é", 12])
def test_nom_de_commande_mal_forme_422(client, games_db, bot, manager, command):
    r = client.post("/admin/games", json={**NEW, "command_name": command})
    assert r.status_code == 422 and "Nom de commande invalide" in r.json()["detail"]
    assert not [c for c in bot["calls"] if c[1] == "/games/taken"]


@pytest.mark.parametrize("emoji", ["apex", "🎯🎯", "🎯 🔫", ":fire:", "", None, "<:x:12>"])
def test_emoji_invalide_422(client, games_db, bot, manager, emoji):
    r = client.post("/admin/games", json={**NEW, "emoji": emoji})
    assert r.status_code == 422 and r.json()["detail"].startswith("Émoji invalide")
    assert not _game_writes(games_db)


@pytest.mark.parametrize("emoji", ["🔪", "⚔", "⚔️", "⭐", "📺", "🎭"])
def test_emoji_deja_utilise_422(client, games_db, bot, manager, emoji):
    """Jeux en base (avec ou sans VS16) et rôles de notification du message de réactions."""
    r = client.post("/admin/games", json={**NEW, "emoji": emoji})
    assert r.status_code == 422 and r.json()["detail"] == f"L'émoji {emoji} est déjà utilisé."
    assert not _game_writes(games_db)


def test_emoji_personnalise_trop_long_422(client, games_db, bot, manager):
    r = client.post("/admin/games", json={**NEW, "emoji": "<:" + "a" * 32 + ":123456789012345678>"})
    assert r.status_code == 422 and "32 caractères" in r.json()["detail"]


def test_emoji_personnalise_accepte(client, games_db, bot, manager):
    r = client.post("/admin/games", json={**NEW, "emoji": " <:apex:123456789012345678> "})
    assert r.status_code == 201
    assert _game_writes(games_db)[0][1][8] == "<:apex:123456789012345678>"


def test_bot_injoignable_nom_non_verifiable_503(client, games_db, bot, manager):
    bot["responses"][("get", "/games/taken")] = HTTPException(503, "Gestion des jeux non chargée")
    r = client.post("/admin/games", json=NEW)
    assert r.status_code == 503 and "/apex" in r.json()["detail"]
    assert not _game_writes(games_db)


def test_course_sur_le_nom_de_commande_422(client, games_db, bot, manager):
    def race(sql, *args):
        error = asyncpg.UniqueViolationError("doublon")
        error.constraint_name = "site_games_command_name_key"
        raise error

    games_db.rules.insert(0, ("insert into site_games", race))
    r = client.post("/admin/games", json=NEW)
    assert r.status_code == 422 and r.json()["detail"] == "La commande /apex existe déjà."


# ── Modification ─────────────────────────────────────────────────────────────

def test_modification_emoji_commande_cooldown(client, games_db, bot, manager):
    r = client.put("/admin/games/lol", json={"emoji": "🗡️", "command_name": "league", "lfg_cooldown": 1800})
    assert r.status_code == 200 and r.json() == {"ok": True, "bot_reloaded": True}
    sql, args = _game_writes(games_db)[0]
    assert "emoji = $2" in sql and "command_name = $3" in sql and "lfg_cooldown = $4" in sql
    assert args == ("lol", "🗡️", "league", 1800)
    taken_call = next(c for c in bot["calls"] if c[1] == "/games/taken")
    assert taken_call[3]["params"] == {"exclude": "lol"}
    assert ("post", "/games/reload") in [(c[0], c[1]) for c in bot["calls"]]
    (row,) = _audit(games_db)
    assert row["kind"] == "game" and row["action"] == "game_update" and row["target_name"] == "League of Legends"
    assert row["details"] == {"key": "lol", "changes": {"emoji": "🗡️", "command_name": "league",
                                                        "lfg_cooldown": 1800}}


def test_modification_garde_son_propre_nom_et_emoji(client, games_db, bot, manager):
    r = client.put("/admin/games/lol", json={"emoji": "⚔️", "command_name": "lol"})
    assert r.status_code == 200


def test_modification_nom_d_un_autre_jeu_422(client, games_db, bot, manager):
    r = client.put("/admin/games/lol", json={"command_name": "dbd"})
    assert r.status_code == 422 and r.json()["detail"] == "La commande /dbd existe déjà."
    r = client.put("/admin/games/lol", json={"emoji": "🚀"})
    assert r.status_code == 422 and r.json()["detail"] == "L'émoji 🚀 est déjà utilisé."
    assert not _game_writes(games_db)


@pytest.mark.parametrize("cooldown", [0, 59, 86_401, -1, "3600", True, 1.5])
def test_cooldown_invalide_422(client, games_db, bot, manager, cooldown):
    r = client.put("/admin/games/lol", json={"lfg_cooldown": cooldown})
    assert r.status_code == 422 and not _game_writes(games_db)


@pytest.mark.parametrize("cooldown", [60, 86_400])
def test_cooldown_bornes_incluses(client, games_db, bot, manager, cooldown):
    assert client.put("/admin/games/lol", json={"lfg_cooldown": cooldown}).status_code == 200


def test_modification_jeu_inconnu_404(client, games_db, bot, manager):
    assert client.put("/admin/games/nope", json={"emoji": "🎯"}).status_code == 404


def test_modification_sans_emoji_ni_commande_n_interroge_pas_le_bot(client, games_db, bot, manager):
    assert client.put("/admin/games/lol", json={"tagline": "x"}).status_code == 200
    assert not [c for c in bot["calls"] if c[1] == "/games/taken"]


# ── Désactivation / réactivation ─────────────────────────────────────────────

def test_desactivation_archive_puis_masque_du_site(client, games_db, bot, manager):
    bot_client._cache["staff"] = (10**12, ["périmé"])
    r = client.delete("/admin/games/lol")
    assert r.status_code == 200
    assert r.json() == {"ok": True, "status": {"role": "ok", "forum": "ok", "command": "none"}}
    call = next(c for c in bot["calls"] if c[1] == "/games/lol/archive")
    assert call[0] == "post" and call[2] == content.GAME_ACTION_TIMEOUT
    sql, args = _game_writes(games_db)[0]
    assert "active = false" in sql.lower() and "delete" not in sql.lower() and args == ("lol",)
    assert "staff" not in bot_client._cache
    assert [(a["kind"], a["action"], a["success"]) for a in _audit(games_db)] == [("game", "game_archive", True)]


def test_reactivation(client, games_db, bot, manager):
    r = client.post("/admin/games/lol/reactivate")
    assert r.status_code == 200 and r.json()["status"]["command"] == "ok"
    assert ("post", "/games/lol/unarchive") in [(c[0], c[1]) for c in bot["calls"]]
    sql, _ = _game_writes(games_db)[0]
    assert "active = true" in sql.lower()
    assert _audit(games_db)[0]["action"] == "game_reactivate"


@pytest.mark.parametrize("method,url", [("delete", "/admin/games/nope"),
                                        ("post", "/admin/games/nope/reactivate"),
                                        ("post", "/admin/games/nope/provision")])
def test_jeu_inconnu_404_sans_appel_au_bot(client, games_db, bot, manager, method, url):
    r = client.request(method.upper(), url)
    assert r.status_code == 404 and r.json()["detail"] == "Jeu inconnu"
    assert not bot["calls"] and not _audit(games_db)


def test_desactivation_refusee_par_discord_relayee_et_journalisee(client, games_db, bot, manager):
    detail = "Permission refusée — le bot n'a pas les droits nécessaires (Gérer les rôles, Gérer les salons)"
    bot["responses"][("post", "/games/lol/archive")] = HTTPException(403, detail)
    r = client.delete("/admin/games/lol")
    assert r.status_code == 403 and r.json()["detail"] == detail
    assert not _game_writes(games_db)  # le site garde le jeu visible : rien n'est masqué à moitié
    (row,) = _audit(games_db)
    assert (row["kind"], row["action"], row["success"]) == ("game", "game_archive", False)
    assert row["details"] == {"key": "lol", "error": detail}


# ── Provisionnement ──────────────────────────────────────────────────────────

def test_provision_renvoie_le_recapitulatif(client, games_db, bot, manager):
    r = client.post("/admin/games/lol/provision")
    assert r.status_code == 200
    assert r.json() == {"role_id": "11", "forum_id": "22", "command": "lol", "created": ["forum"],
                        "status": {"role": "ok", "forum": "ok", "command": "ok"}}
    call = next(c for c in bot["calls"] if c[1] == "/games/lol/provision")
    assert call[2] == content.GAME_ACTION_TIMEOUT > 10  # plus long que le délai par défaut
    (row,) = _audit(games_db)
    assert row["kind"] == "game" and row["action"] == "game_provision" and row["success"] is True
    assert row["details"] == {"key": "lol", "created": ["forum"], "role_id": "11", "forum_id": "22",
                              "command": "lol"}


@pytest.mark.parametrize("error,status,detail", [
    (HTTPException(403, "Permission refusée — le bot n'a pas les droits nécessaires"), 403,
     "Permission refusée — le bot n'a pas les droits nécessaires"),
    (HTTPException(404, "Rôle ou salon Discord introuvable"), 404, "Rôle ou salon Discord introuvable"),
    (HTTPException(502, "Erreur Discord : boom"), 502, "Erreur Discord : boom"),
    (HTTPException(503, "Serveur Discord introuvable"), 503, "Serveur Discord introuvable"),
    (httpx.ReadTimeout("lent"), 504, None),
    (httpx.ConnectError("refusé"), 503, "Bot injoignable : réessayez dans un instant"),
])
def test_provision_erreurs_relayees_et_journalisees(client, games_db, bot, manager, error, status, detail):
    bot["responses"][("post", "/games/lol/provision")] = error
    r = client.post("/admin/games/lol/provision")
    assert r.status_code == status
    if detail:
        assert r.json()["detail"] == detail
    else:
        assert r.json()["detail"].startswith("Le bot n'a pas répondu à temps")
    (row,) = _audit(games_db)
    assert (row["kind"], row["action"], row["success"]) == ("game", "game_provision", False)
    assert row["details"]["error"] == r.json()["detail"]


# ── Resynchronisation des permissions ────────────────────────────────────────

def test_resync_apercu(client, games_db, bot, session_with):
    session_with(is_admin=True)
    assert client.get("/admin/games/resync-permissions").json() == {"forums": 6}


def test_resync_confirmee(client, games_db, bot, session_with):
    session_with(is_admin=True)
    r = client.post("/admin/games/resync-permissions", json={"confirm_forums": 6})
    assert r.status_code == 200 and r.json() == {"ok": True, "forums": 6}
    call = next(c for c in bot["calls"] if c[1] == "/games/resync-permissions")
    assert call[2] == content.GAME_RESYNC_TIMEOUT
    (row,) = _audit(games_db)
    assert (row["kind"], row["action"], row["details"]) == ("game", "game_resync_permissions", {"forums": 6})


def test_resync_nombre_change_409_sans_ecriture(client, games_db, bot, session_with):
    session_with(is_admin=True)
    r = client.post("/admin/games/resync-permissions", json={"confirm_forums": 5})
    assert r.status_code == 409 and "6 forum(s)" in r.json()["detail"]
    assert ("post", "/games/resync-permissions") not in [(c[0], c[1]) for c in bot["calls"]]
    assert not _audit(games_db)


def test_resync_sans_confirmation_422(client, games_db, bot, session_with):
    session_with(is_admin=True)
    assert client.post("/admin/games/resync-permissions", json={}).status_code == 422


def test_resync_refusee_journalisee(client, games_db, bot, session_with):
    session_with(is_admin=True)
    bot["responses"][("post", "/games/resync-permissions")] = HTTPException(403, "Permission refusée")
    r = client.post("/admin/games/resync-permissions", json={"confirm_forums": 6})
    assert r.status_code == 403
    (row,) = _audit(games_db)
    assert row["success"] is False and row["details"] == {"forums": 6, "error": "Permission refusée"}


def test_actions_de_jeu_classees_game():
    for action in ("game_create", "game_update", "game_provision", "game_archive", "game_reactivate",
                   "game_resync_permissions"):
        assert admin.KIND_OF_ACTION[action] == "game"
