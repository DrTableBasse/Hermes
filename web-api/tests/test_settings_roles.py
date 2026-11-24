"""Réglages qui désignent un rôle : réservés au propriétaire et aux admins (constat I2).

``settings.manage`` seul ne doit pas permettre de nommer son propre rôle ``admin_role`` (tous les
droits du site), ``mod_role``/``authorized_roles`` (droits des commandes du bot), ni un rôle que le
bot attribue tout seul (niveaux, bump) : ce serait contourner l'anti-escalade.
"""
import pytest

import bot_client
from settings_registry import G_ROLES, SETTINGS

ROLE_SETTINGS = sorted(k for k, d in SETTINGS.items() if d.group == G_ROLES or d.kind == "role")
DETAIL = "Réservé aux administrateurs : ce réglage désigne un rôle qui donne des droits"


@pytest.fixture(autouse=True)
def _bot_offline(monkeypatch):
    async def fake_post(path, json=None, timeout=1.5):
        return {"ok": True}

    monkeypatch.setattr(bot_client, "bot_post", fake_post)


def _writes(fake_db):
    return [c for c in fake_db.calls if c[0] == "execute" and "bot_settings" in c[1]]


def test_la_liste_couvre_les_reglages_de_roles_attendus():
    assert {"admin_role", "mod_role", "authorized_roles", "role_level_5", "bump_role"} <= set(ROLE_SETTINGS)


@pytest.mark.parametrize("key", ROLE_SETTINGS)
@pytest.mark.parametrize("value", ["123", ""])
def test_settings_manage_seul_refuse(client, fake_db, session_with, key, value):
    session_with({"settings.manage", "permissions.manage"})
    r = client.put(f"/admin/settings/{key}", json={"value": value})
    assert r.status_code == 403
    assert r.json()["detail"] == DETAIL
    assert _writes(fake_db) == []


@pytest.mark.parametrize("key", ["admin_role", "mod_role", "authorized_roles", "bump_role"])
def test_admin_peut_regler_les_roles(client, fake_db, session_with, key):
    session_with((), is_admin=True)
    r = client.put(f"/admin/settings/{key}", json={"value": "123"})
    assert r.status_code == 200
    assert _writes(fake_db)


def test_settings_manage_regle_toujours_les_autres_reglages(client, fake_db, session_with):
    session_with({"settings.manage"})
    r = client.put("/admin/settings/bump_role_threshold", json={"value": "5"})
    assert r.status_code == 200


def test_liste_signale_les_reglages_reserves(client, fake_db, session_with, monkeypatch):
    async def fake_get(path, timeout=1.5):
        return None

    monkeypatch.setattr(bot_client, "bot_get", fake_get)
    session_with({"settings.manage"})
    items = {i["key"]: i for g in client.get("/admin/settings").json()["groups"] for i in g["items"]}
    assert items["admin_role"]["admin_only"] is True
    assert items["bump_role"]["admin_only"] is True
    assert items["welcome_channel"]["admin_only"] is False


# ── I3 : redacteur_role remplacé par la page Accès ───────────────────────────

def test_redacteur_role_absent_de_la_liste(client, fake_db, session_with, monkeypatch):
    async def fake_get(path, timeout=1.5):
        return None

    monkeypatch.setattr(bot_client, "bot_get", fake_get)
    session_with((), is_admin=True)
    keys = {i["key"] for g in client.get("/admin/settings").json()["groups"] for i in g["items"]}
    assert "redacteur_role" not in keys
    assert "admin_role" in keys


def test_redacteur_role_non_modifiable_meme_admin(client, fake_db, session_with):
    session_with((), is_admin=True)
    r = client.put("/admin/settings/redacteur_role", json={"value": "123"})
    assert r.status_code == 409
    assert r.json()["detail"] == "Réglage remplacé par la page Accès (/admin/acces)"
    assert _writes(fake_db) == []


# ── Étape 3, I3 : réglages remplacés par les règles automatiques ────────────

RULE_SUPERSEDED = ("role_batman", "role_level_5", "role_level_10", "role_level_20", "role_level_50",
                   "voice_hours_for_role")


def test_reglages_remplaces_par_les_regles_absents_de_la_liste(client, fake_db, session_with, monkeypatch):
    async def fake_get(path, timeout=1.5):
        return None

    monkeypatch.setattr(bot_client, "bot_get", fake_get)
    session_with((), is_admin=True)
    keys = {i["key"] for g in client.get("/admin/settings").json()["groups"] for i in g["items"]}
    assert keys.isdisjoint(RULE_SUPERSEDED)
    assert "bump_role" in keys


@pytest.mark.parametrize("key", RULE_SUPERSEDED)
def test_reglages_remplaces_par_les_regles_non_modifiables(client, fake_db, session_with, key):
    session_with((), is_admin=True)
    r = client.put(f"/admin/settings/{key}", json={"value": "123"})
    assert r.status_code == 409
    assert r.json()["detail"] == "Réglage remplacé par les règles automatiques (/admin/regles)"
    assert _writes(fake_db) == []
