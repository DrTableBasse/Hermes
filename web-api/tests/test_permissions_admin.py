"""Permissions des rôles Discord et accès aux commandes (étape 6, tâche 3) : droits, anti-escalade
(Review Focus 1 et 2), propriétaire, commande admin, transaction, rechargement du bot, journal."""
import json
import re
from pathlib import Path

import httpx
import pytest
from fastapi import HTTPException

import database
import discord_permissions as dp
from limiter import limiter
from routes import admin

B = dp.BITS
EVERY = dp.CATALOG_MASK
EXTRA_BIT = 1 << 60  # bit hors catalogue déjà posé sur un rôle

# Rôles du plus haut au plus bas (forme de GET /discord/roles/permissions).
PERM_ROLES = [
    {"id": "900", "name": "Bot", "position": 12, "managed": True, "is_default": False, "permissions": EVERY},
    {"id": "800", "name": "Fondateur", "position": 11, "managed": False, "is_default": False,
     "permissions": B["administrator"]},
    {"id": "500", "name": "Chef", "position": 10, "managed": False, "is_default": False, "permissions": 0},
    {"id": "400", "name": "Modo", "position": 5, "managed": False, "is_default": False,
     "permissions": B["kick_members"] | B["manage_messages"]},
    {"id": "300", "name": "Ancien admin", "position": 3, "managed": False, "is_default": False,
     "permissions": B["administrator"] | B["kick_members"]},
    {"id": "250", "name": "Booster", "position": 2, "managed": True, "is_default": False, "permissions": 0},
    {"id": "200", "name": "Membre", "position": 1, "managed": False, "is_default": False,
     "permissions": B["send_messages"] | EXTRA_BIT},
    {"id": "100", "name": "@everyone", "position": 0, "managed": False, "is_default": True,
     "permissions": B["view_channel"]},
]

# Forme de GET /discord/roles (rôles de l'étape 3, @everyone jamais listé).
ROLES = [
    {"id": "800", "name": "Fondateur", "color": 1, "position": 11, "managed": False, "members": 1, "below_bot": True},
    {"id": "500", "name": "Chef", "color": 1, "position": 10, "managed": False, "members": 2, "below_bot": True},
    {"id": "400", "name": "Modo", "color": 2, "position": 5, "managed": False, "members": 3, "below_bot": True},
    {"id": "200", "name": "Membre", "color": 3, "position": 1, "managed": False, "members": 37, "below_bot": True},
]

CATALOG = [
    {"name": "blague", "description": "Une blague", "admin_only": False, "native_protected": False},
    {"name": "kick", "description": "Expulser", "admin_only": True, "native_protected": False},
    {"name": "ticket", "description": "Tickets", "admin_only": False, "native_protected": True},
]

# Modérateur : rang 7 (sous Chef), possède Expulser + Gérer les messages, PAS Bannir.
MOD_PERMS = B["kick_members"] | B["manage_messages"] | B["send_messages"] | B["view_channel"]


class FakeConn:
    """Connexion asyncpg factice : transaction enregistrée, échec programmable."""

    def __init__(self, log, fail=False):
        self.log, self.fail = log, fail

    def transaction(self):
        conn = self

        class _Tx:
            async def __aenter__(self):
                conn.log.append(("begin",))

            async def __aexit__(self, exc_type, *_):
                conn.log.append(("rollback",) if exc_type else ("commit",))
                return False

        return _Tx()

    async def execute(self, sql, *args):
        self.log.append(("execute", sql, args))

    async def executemany(self, sql, rows):
        if self.fail:
            raise RuntimeError("panne")
        self.log.append(("executemany", sql, rows))


@pytest.fixture
def bot(monkeypatch, fake_db):
    """Bot factice + table ``command_permissions`` en mémoire."""
    state = {
        "actor": {"permissions": MOD_PERMS, "top_position": 7, "is_owner": False},
        # Le modérateur porte Modo et Membre (sous son rôle le plus haut, rang 7).
        "rank": {"top_position": 7, "is_owner": False, "role_ids": ["400", "200"]},
        "calls": [], "errors": {},
        "allowed": [("kick", 400)],
        "tx": [], "tx_fail": False,
    }

    async def fake_bot(method, path, **kwargs):
        state["calls"].append((method, path, kwargs.get("json"), kwargs.get("params")))
        if (method, path) in state["errors"]:
            raise state["errors"][(method, path)]
        if path == "/discord/roles/permissions":
            return {"roles": [dict(r) for r in PERM_ROLES], "actor": dict(state["actor"]),
                    "bot": {"top_position": 12}}
        if path.startswith("/discord/roles/") and method == "patch":
            role = next(r for r in PERM_ROLES if r["id"] == path.split("/")[3])
            after = kwargs["json"]["permissions"] | (role["permissions"] & ~EVERY)
            return {"role": {**role, "permissions": after}, "before": role["permissions"], "after": after}
        if path == "/discord/roles":
            return {"roles": ROLES}
        if path.startswith("/discord/members/") and path.endswith("/rank"):
            return dict(state["rank"])
        if path == "/commands/catalog":
            return {"commands": [dict(c) for c in CATALOG]}
        if path == "/command-permissions/reload":
            return {"ok": True, "restricted": 1}
        raise AssertionError(f"appel bot inattendu : {method} {path}")

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def fake_conn():
        yield FakeConn(state["tx"], fail=state["tx_fail"])

    monkeypatch.setattr(admin, "_bot", fake_bot)
    monkeypatch.setattr(database, "get_conn", fake_conn)
    monkeypatch.setattr(limiter, "enabled", False)
    fake_db.on("from command_permissions",
               lambda sql, *a: [{"command_name": c, "role_id": r} for c, r in state["allowed"]])
    fake_db.on("from user_voice_data", {"name": "Bob"})
    return state


@pytest.fixture
def mod(session_with, bot):
    return session_with({"permissions.manage"})


def _audit(fake_db):
    rows = []
    for method, sql, args in fake_db.calls:
        if method == "execute" and "insert into audit_events" in sql.lower():
            kind, action, source, actor_id, _name, target_id, target_name, details, success = args
            rows.append({"kind": kind, "action": action, "actor_id": actor_id, "target_id": target_id,
                         "target_name": target_name, "details": json.loads(details), "success": success})
    return rows


def _patches(bot):
    return [c for c in bot["calls"] if c[0] == "patch"]


def _flags(role_id):
    role = next(r for r in PERM_ROLES if r["id"] == role_id)
    return sorted(dp.value_to_flags(role["permissions"]))


# ── Catalogue : copie fidèle de bot/utils/permission_catalog.py ────────────

BOT_CATALOG = Path(__file__).resolve().parents[2] / "bot" / "utils" / "permission_catalog.py"


@pytest.mark.skipif(not BOT_CATALOG.exists(), reason="code du bot absent (image web-api)")
def test_catalog_matches_bot_families_keys_and_labels():
    source = BOT_CATALOG.read_text(encoding="utf-8")
    bot_families = []
    for block in re.finditer(r'\("([^"]+)", \[\n(.*?)\n    \]\)', source, re.S):
        items = re.findall(r'\("([a-z_]+)", "([^"]+)"\)', block.group(2))
        bot_families.append((block.group(1), items))
    mine = [(fam, [(k, label) for k, label, _ in items]) for fam, items in dp.FAMILIES]
    assert bot_families == mine
    # Même règle d'anti-escalade, texte compris.
    for marker in ("Seul le propriétaire du serveur peut accorder la permission « Administrateur ».",
                   "Tu ne peux pas {verbe} la permission « {_LABELS[flag]} » : tu ne la possèdes pas."):
        assert marker in source


def test_catalog_bits_match_discord_py():
    discord = pytest.importorskip("discord")
    for flag, bit in dp.BITS.items():
        assert discord.Permissions.VALID_FLAGS[flag] == bit, flag
    every_bit = {bit for bit in discord.Permissions.VALID_FLAGS.values()}
    assert every_bit == set(dp.BITS.values())  # aucun drapeau de discord.py oublié


# ── Droits ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("method,path,body", [
    ("get", "/admin/permissions/discord", None),
    ("put", "/admin/permissions/discord/400", {"permissions": []}),
    ("get", "/admin/permissions/commands", None),
    ("put", "/admin/permissions/commands/blague", {"role_ids": []}),
])
def test_permission_required(session_with, bot, method, path, body):
    client = session_with({"roles.manage", "channels.manage"})
    r = client.request(method, path, json=body)
    assert r.status_code == 403
    assert r.json()["detail"] == "Droit requis : Gérer les accès"
    assert bot["calls"] == []


# ── Lecture Discord ─────────────────────────────────────────────────────────

def test_read_discord_marks_editable_roles_and_flags(mod, bot):
    r = mod.get("/admin/permissions/discord")
    assert r.status_code == 200
    data = r.json()
    assert bot["calls"][0][3] == {"actor_id": "1"}
    assert [f["family"] for f in data["families"]] == ["Général", "Membres", "Messages", "Vocal",
                                                        "Événements", "Avancé"]
    roles = {r["id"]: r for r in data["roles"]}
    assert [r["id"] for r in data["roles"]] == [r["id"] for r in PERM_ROLES]
    assert {i for i, r in roles.items() if r["editable"]} == {"400", "300", "200"}
    assert roles["900"]["refusal"] == "Ce rôle est géré par une intégration et ne peut pas être modifié"
    assert roles["500"]["refusal"] == "Ce rôle n'est pas sous votre rôle le plus haut"
    assert roles["100"]["refusal"] == "Seul le propriétaire du serveur peut modifier les permissions de @everyone"
    # Un modérateur ne bascule que ce qu'il possède ; jamais Bannir ni Administrateur.
    assert set(roles["400"]["editable_flags"]) == dp.value_to_flags(MOD_PERMS)
    assert roles["400"]["permissions"] == ["kick_members", "manage_messages"]
    # Bit hors catalogue jamais exposé.
    assert roles["200"]["permissions"] == ["send_messages"]
    # « Administrateur » déjà posé sur un rôle sous lui : il ne peut pas le retirer (Focus 2).
    assert "administrator" not in roles["300"]["editable_flags"]
    assert roles["500"]["editable_flags"] == []
    assert data["actor"] == {"is_owner": False, "top_position": 7,
                             "permissions": sorted(dp.value_to_flags(MOD_PERMS)), "is_admin": False}


def test_read_discord_owner_edits_everyone_but_not_managed_or_above_bot(mod, bot):
    bot["actor"] = {"permissions": EVERY, "top_position": 11, "is_owner": True}
    roles = {r["id"]: r for r in mod.get("/admin/permissions/discord").json()["roles"]}
    assert {i for i, r in roles.items() if r["editable"]} == {"800", "500", "400", "300", "200", "100"}
    assert not roles["900"]["editable"] and not roles["250"]["editable"]  # managed : limite Discord
    assert set(roles["100"]["editable_flags"]) == set(dp.BITS)  # Administrateur compris (confirmation)


# ── Écriture Discord : anti-escalade ────────────────────────────────────────

def test_focus1_moderator_cannot_grant_ban_he_lacks(mod, bot, fake_db):
    r = mod.put("/admin/permissions/discord/200", json={"permissions": ["send_messages", "ban_members"]})
    assert r.status_code == 403
    assert r.json()["detail"] == ("Tu ne peux pas accorder la permission « Bannir des membres » : "
                                  "tu ne la possèdes pas.")
    assert _patches(bot) == [] and _audit(fake_db) == []


def test_focus2_cannot_remove_administrator_from_role_below(mod, bot, fake_db):
    r = mod.put("/admin/permissions/discord/300", json={"permissions": ["kick_members"]})
    assert r.status_code == 403
    assert r.json()["detail"] == ("Tu ne peux pas retirer la permission « Administrateur » : "
                                  "tu ne la possèdes pas.")
    assert _patches(bot) == []


def test_cannot_remove_permission_actor_lacks(mod, bot):
    bot["actor"]["permissions"] = B["send_messages"]
    r = mod.put("/admin/permissions/discord/400", json={"permissions": ["manage_messages"]})
    assert r.status_code == 403
    assert "retirer la permission « Expulser des membres »" in r.json()["detail"]
    assert _patches(bot) == []


def test_non_owner_cannot_grant_administrator_even_as_administrator(mod, bot):
    bot["actor"]["permissions"] = B["administrator"]
    r = mod.put("/admin/permissions/discord/200",
                json={"permissions": ["send_messages", "administrator"], "confirm_administrator": True})
    assert r.status_code == 403
    assert r.json()["detail"] == "Seul le propriétaire du serveur peut accorder la permission « Administrateur »."


def test_administrator_actor_can_toggle_anything_else(mod, bot):
    bot["actor"]["permissions"] = B["administrator"]
    r = mod.put("/admin/permissions/discord/400", json={"permissions": ["ban_members"]})
    assert r.status_code == 200
    assert _patches(bot)[0][2]["permissions"] == B["ban_members"]


@pytest.mark.parametrize("role_id,detail", [
    ("500", "Ce rôle n'est pas sous votre rôle le plus haut"),
    ("250", "Ce rôle est géré par une intégration et ne peut pas être modifié"),
    ("100", "Seul le propriétaire du serveur peut modifier les permissions de @everyone"),
])
def test_role_refusals(mod, bot, role_id, detail):
    r = mod.put(f"/admin/permissions/discord/{role_id}", json={"permissions": []})
    assert r.status_code == 403 and r.json()["detail"] == detail
    assert _patches(bot) == []


def test_unknown_flag_and_unknown_role(mod, bot):
    r = mod.put("/admin/permissions/discord/400", json={"permissions": ["fly"]})
    assert r.status_code == 422 and r.json()["detail"] == "Permission inconnue : fly"
    r = mod.put("/admin/permissions/discord/999", json={"permissions": []})
    assert r.status_code == 404


# ── Propriétaire ────────────────────────────────────────────────────────────

@pytest.fixture
def owner(mod, bot):
    bot["actor"] = {"permissions": EVERY, "top_position": 11, "is_owner": True}
    return mod


def test_owner_exempt_edits_everyone_and_role_at_top(owner, bot):
    assert owner.put("/admin/permissions/discord/100", json={"permissions": ["view_channel", "connect"]}
                     ).status_code == 200
    assert owner.put("/admin/permissions/discord/800", json={"permissions": []}).status_code == 200


def test_owner_still_refused_managed_and_above_bot(owner, bot):
    r = owner.put("/admin/permissions/discord/900", json={"permissions": []})
    assert r.status_code == 403
    assert _patches(bot) == []


def test_owner_administrator_requires_confirmation(owner, bot, fake_db):
    body = {"permissions": ["send_messages", "administrator"]}
    r = owner.put("/admin/permissions/discord/200", json=body)
    assert r.status_code == 422 and r.json()["detail"] == "Activer « Administrateur » demande une confirmation explicite"
    assert _patches(bot) == []
    r = owner.put("/admin/permissions/discord/200", json={**body, "confirm_administrator": True})
    assert r.status_code == 200
    assert _patches(bot)[0][2]["confirm_administrator"] is True


# ── Écriture Discord : succès, journal ──────────────────────────────────────

def test_update_sends_catalog_bits_and_logs_readable_before_after(mod, bot, fake_db):
    r = mod.put("/admin/permissions/discord/200", json={"permissions": ["send_messages", "kick_members"]})
    assert r.status_code == 200
    assert r.json()["changed"] is True
    assert r.json()["role"]["permissions"] == ["kick_members", "send_messages"]  # forme de la lecture
    assert r.json()["role"]["editable"] is True
    _, path, payload, _ = _patches(bot)[0]
    assert path == "/discord/roles/200/permissions"
    assert payload == {"actor_id": "1", "actor_name": "Bob", "confirm_administrator": False,
                       "permissions": B["send_messages"] | B["kick_members"]}  # jamais de bit hors catalogue
    [row] = _audit(fake_db)
    assert row["kind"] == "permission" and row["action"] == "role_permissions_update" and row["success"]
    assert row["target_id"] == 200 and row["target_name"] == "Membre"
    assert row["details"] == {"role": "Membre", "before": ["Envoyer des messages"],
                              "after": ["Expulser des membres", "Envoyer des messages"],
                              "added": ["Expulser des membres"], "removed": []}


def test_update_without_change_calls_nothing(mod, bot, fake_db):
    r = mod.put("/admin/permissions/discord/400", json={"permissions": ["manage_messages", "kick_members"]})
    assert r.status_code == 200 and r.json()["changed"] is False
    assert r.json()["role"]["permissions"] == ["kick_members", "manage_messages"]
    assert _patches(bot) == [] and _audit(fake_db) == []


def test_bot_refusal_is_relayed_and_logged(mod, bot, fake_db):
    bot["errors"][("patch", "/discord/roles/200/permissions")] = HTTPException(
        403, "Le bot n'a pas la permission Discord nécessaire (Gérer les rôles)")
    r = mod.put("/admin/permissions/discord/200", json={"permissions": []})
    assert r.status_code == 403
    assert r.json()["detail"] == "Le bot n'a pas la permission Discord nécessaire (Gérer les rôles)"
    [row] = _audit(fake_db)
    assert row["success"] is False and row["details"]["removed"] == ["Envoyer des messages"]
    assert row["details"]["error"].startswith("Le bot n'a pas")


def test_bot_unreachable_is_translated(mod, bot):
    bot["errors"][("get", "/discord/roles/permissions")] = httpx.ConnectError("boom")
    r = mod.get("/admin/permissions/discord")
    assert r.status_code == 503 and r.json()["detail"] == "Bot injoignable : réessayez dans un instant"


# ── Commandes Hermes : lecture ──────────────────────────────────────────────

def test_read_commands(mod, bot):
    bot["allowed"] = [("blague", 200), ("blague", 777), ("kick", 400)]
    data = mod.get("/admin/permissions/commands").json()
    cmds = {c["name"]: c for c in data["commands"]}
    assert cmds["blague"]["roles"] == [{"id": "200", "name": "Membre", "deleted": False},
                                       {"id": "777", "name": None, "deleted": True}]
    assert cmds["ticket"]["roles"] == [] and cmds["ticket"]["native_protected"] is True
    assert cmds["kick"]["admin_only"] is True and cmds["kick"]["editable"] is False
    assert cmds["blague"]["editable"] is True
    assignable = {r["id"]: r["assignable"] for r in data["roles"]}
    assert assignable == {"800": False, "500": False, "400": True, "200": True}
    assert data["actor"] == {"is_owner": False, "top_position": 7, "is_admin": False}


# ── Commandes Hermes : écriture ─────────────────────────────────────────────

def test_replace_list_in_transaction_reloads_and_logs(mod, bot, fake_db):
    bot["allowed"] = [("blague", 200)]
    r = mod.put("/admin/permissions/commands/blague", json={"role_ids": ["400", "400", "200"]})
    assert r.status_code == 200
    assert r.json() == {"command": "blague", "role_ids": ["400", "200"], "changed": True, "reload_failed": False}
    assert bot["tx"][0] == ("begin",) and bot["tx"][-1] == ("commit",)
    assert bot["tx"][1] == ("execute", "DELETE FROM command_permissions WHERE command_name = $1", ("blague",))
    assert bot["tx"][2][2] == [("blague", 400), ("blague", 200)]
    assert ("post", "/command-permissions/reload", None, None) in bot["calls"]
    [row] = _audit(fake_db)
    assert row["kind"] == "permission" and row["action"] == "command_permissions_update" and row["success"]
    assert row["target_name"] == "/blague"
    assert row["details"] == {"command": "blague", "before": ["Membre"], "after": ["Modo", "Membre"],
                              "added": ["Modo"], "removed": [], "reload_failed": False}


def test_identical_put_still_reloads_without_new_audit(mod, bot, fake_db):
    bot["allowed"] = [("blague", 200)]
    r = mod.put("/admin/permissions/commands/blague", json={"role_ids": ["200"]})
    assert r.status_code == 200
    assert r.json() == {"command": "blague", "role_ids": ["200"], "changed": False, "reload_failed": False}
    assert ("post", "/command-permissions/reload", None, None) in bot["calls"]
    assert bot["tx"] == [] and _audit(fake_db) == []


def test_identical_put_reports_reload_failure(mod, bot):
    bot["allowed"] = [("blague", 200)]
    bot["errors"][("post", "/command-permissions/reload")] = HTTPException(503, "Lecture impossible")
    r = mod.put("/admin/permissions/commands/blague", json={"role_ids": ["200"]})
    assert r.status_code == 200
    assert r.json()["changed"] is False and r.json()["reload_failed"] is True


def test_emptied_list_deletes_all_rows(mod, bot):
    bot["allowed"] = [("blague", 200)]
    r = mod.put("/admin/permissions/commands/blague", json={"role_ids": []})
    assert r.status_code == 200 and r.json()["role_ids"] == []
    assert [e[0] for e in bot["tx"]] == ["begin", "execute", "commit"]


def test_reload_failure_keeps_list_and_flags_it(mod, bot, fake_db):
    bot["errors"][("post", "/command-permissions/reload")] = HTTPException(503, "Lecture impossible")
    r = mod.put("/admin/permissions/commands/blague", json={"role_ids": ["200"]})
    assert r.status_code == 200 and r.json()["reload_failed"] is True
    assert bot["tx"][-1] == ("commit",)
    [row] = _audit(fake_db)
    assert row["success"] is True and row["details"]["reload_failed"] is True


def test_reload_unreachable_also_flagged(mod, bot):
    bot["errors"][("post", "/command-permissions/reload")] = httpx.ConnectError("boom")
    r = mod.put("/admin/permissions/commands/blague", json={"role_ids": ["200"]})
    assert r.status_code == 200 and r.json()["reload_failed"] is True


def test_storage_failure_rolls_back_logs_and_skips_reload(mod, bot, fake_db):
    bot["tx_fail"] = True
    r = mod.put("/admin/permissions/commands/blague", json={"role_ids": ["200"]})
    assert r.status_code == 500
    assert bot["tx"][-1] == ("rollback",)
    assert all(c[1] != "/command-permissions/reload" for c in bot["calls"])
    assert _audit(fake_db)[0]["success"] is False


def test_unknown_command_404(mod, bot):
    r = mod.put("/admin/permissions/commands/nope", json={"role_ids": []})
    assert r.status_code == 404 and r.json()["detail"] == "Commande introuvable"
    assert bot["tx"] == []


def test_admin_command_reserved_to_site_admins(mod, bot, session_with, fake_db):
    r = mod.put("/admin/permissions/commands/kick", json={"role_ids": ["400", "200"]})
    assert r.status_code == 403
    assert r.json()["detail"] == ("Seul un administrateur du site peut modifier l'accès à une commande "
                                  "réservée aux admins")
    assert bot["tx"] == []
    admin_client = session_with(is_admin=True)
    assert admin_client.put("/admin/permissions/commands/kick", json={"role_ids": ["400", "200"]}
                            ).status_code == 200


@pytest.mark.parametrize("before,role_ids", [
    ([], ["500"]),              # ajouter un rôle au-dessus
    ([("blague", 500)], []),    # retirer un rôle au-dessus
])
def test_role_above_actor_refused(mod, bot, before, role_ids):
    bot["allowed"] = before
    r = mod.put("/admin/permissions/commands/blague", json={"role_ids": role_ids})
    assert r.status_code == 403
    assert r.json()["detail"] == "Le rôle « Chef » est au niveau du vôtre ou au-dessus : vous ne pouvez pas le modifier"
    assert bot["tx"] == []


def test_role_above_kept_untouched_is_allowed(mod, bot):
    bot["allowed"] = [("blague", 500), ("blague", 200)]
    r = mod.put("/admin/permissions/commands/blague", json={"role_ids": ["500", "200", "400"]})
    assert r.status_code == 200


def test_owner_exempt_for_command_roles(mod, bot):
    bot["rank"] = {"top_position": 11, "is_owner": True}
    assert mod.put("/admin/permissions/commands/blague", json={"role_ids": ["800"]}).status_code == 200


def test_unknown_role_added_404_but_deleted_role_removable(mod, bot):
    r = mod.put("/admin/permissions/commands/blague", json={"role_ids": ["777"]})
    assert r.status_code == 404 and r.json()["detail"] == "Rôle introuvable"
    bot["allowed"] = [("blague", 777), ("blague", 200)]
    r = mod.put("/admin/permissions/commands/blague", json={"role_ids": ["200"]})
    assert r.status_code == 200


def test_invalid_role_id_rejected(mod, bot):
    assert mod.put("/admin/permissions/commands/blague", json={"role_ids": ["abc"]}).status_code == 422


# ── I1 : on ne modifie que l'accès d'une commande qu'on peut soi-même utiliser ──

CANNOT_USE = ("Vous ne pouvez pas modifier l'accès à une commande que vous ne pouvez pas "
              "utiliser vous-même")
SELF_LOCKOUT = ("Cette modification vous retirerait l'accès à la commande : vous ne pouvez pas "
                "vous l'interdire vous-même")


def test_actor_cannot_open_restricted_command_with_a_role_he_carries(mod, bot, fake_db):
    """Scénario de la relecture : /blague restreinte à « Équipe Event » (Chef ici, non porté),
    le modérateur y ajoute « Animateur » (Modo ici), qu'il porte."""
    bot["allowed"] = [("blague", 500)]
    r = mod.put("/admin/permissions/commands/blague", json={"role_ids": ["500", "400"]})
    assert r.status_code == 403 and r.json()["detail"] == CANNOT_USE
    assert bot["tx"] == [] and _audit(fake_db) == []


def test_actor_cannot_restrict_a_command_he_cannot_use(mod, bot):
    bot["rank"] = {"top_position": 7, "is_owner": False, "role_ids": ["400"]}
    bot["allowed"] = [("blague", 200)]
    r = mod.put("/admin/permissions/commands/blague", json={"role_ids": []})
    assert r.status_code == 403 and r.json()["detail"] == CANNOT_USE


def test_actor_cannot_lock_himself_out(mod, bot):
    bot["rank"] = {"top_position": 7, "is_owner": False, "role_ids": ["400"]}
    bot["allowed"] = []
    r = mod.put("/admin/permissions/commands/blague", json={"role_ids": ["200"]})
    assert r.status_code == 403 and r.json()["detail"] == SELF_LOCKOUT
    assert bot["tx"] == []


def test_actor_who_can_use_the_command_may_change_it(mod, bot):
    bot["allowed"] = [("blague", 200)]
    r = mod.put("/admin/permissions/commands/blague", json={"role_ids": ["200", "400"]})
    assert r.status_code == 200 and r.json()["changed"] is True


def test_actor_without_server_roles_cannot_restrict(mod, bot):
    bot["rank"] = {"top_position": 7, "is_owner": False}  # ancienne forme : pas de role_ids
    r = mod.put("/admin/permissions/commands/blague", json={"role_ids": ["200"]})
    assert r.status_code == 403 and r.json()["detail"] == SELF_LOCKOUT


def test_owner_exempt_from_usage_rule(mod, bot):
    bot["rank"] = {"top_position": 11, "is_owner": True, "role_ids": []}
    bot["allowed"] = [("blague", 500)]
    assert mod.put("/admin/permissions/commands/blague", json={"role_ids": ["400"]}).status_code == 200


def test_site_admin_exempt_from_usage_rule(session_with, bot):
    bot["rank"] = {"top_position": 11, "is_owner": False, "role_ids": []}  # au-dessus de Chef
    bot["allowed"] = [("blague", 500)]
    admin_client = session_with(is_admin=True)
    assert admin_client.put("/admin/permissions/commands/blague", json={"role_ids": ["400"]}).status_code == 200
