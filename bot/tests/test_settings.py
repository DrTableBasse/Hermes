"""Tests des modules purs de réglages (aucune connexion Discord ni base)."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import settings_registry as reg  # noqa: E402


def test_validate_rejects_unknown_key():
    with pytest.raises(ValueError):
        reg.validate("n_existe_pas", "1")


def test_validate_int():
    assert reg.validate("bump_role_threshold", " 25 ") == "25"
    for bad in ("abc", "1.5", "-3"):
        with pytest.raises(ValueError):
            reg.validate("bump_role_threshold", bad)


def test_validate_url():
    assert reg.validate("invite_url", "https://discord.gg/abc") == "https://discord.gg/abc"
    for bad in ("ftp://x.y/z", "discord.gg/abc", "javascript:alert(1)", "https://"):
        with pytest.raises(ValueError):
            reg.validate("invite_url", bad)


def test_validate_id():
    assert reg.validate("welcome_channel", "123456789012345678") == "123456789012345678"
    with pytest.raises(ValueError):
        reg.validate("welcome_channel", "salon-accueil")


def test_needs_creation():
    assert reg.needs_channel_creation(None, {1, 2}) is True
    assert reg.needs_channel_creation("", {1, 2}) is True
    assert reg.needs_channel_creation("3", {1, 2}) is True
    assert reg.needs_channel_creation("2", {1, 2}) is False


def test_registries_identical():
    bot_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "utils", "settings_registry.py")
    web_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                            "web-api", "settings_registry.py")
    with open(bot_file, "rb") as a, open(web_file, "rb") as b:
        assert a.read() == b.read()


# ── staff_roles / get_roles (étape 4, tâche 2) ───────────────────────────────

def test_staff_roles_est_dans_le_groupe_roles():
    from utils.settings_registry import G_ROLES, SETTINGS, validate
    assert SETTINGS["staff_roles"].group == G_ROLES
    assert validate("staff_roles", "1, 2") == "1,2"


def test_get_roles_ignore_les_identifiants_perimes_et_les_doublons(monkeypatch):
    from types import SimpleNamespace as N
    from utils import settings

    roles = {10: N(id=10), 20: N(id=20)}
    guild = N(get_role=lambda i: roles.get(i))
    monkeypatch.setitem(settings._cache, "staff_roles", "10, 99,abc,20,10")
    assert [r.id for r in settings.get_roles(guild, "staff_roles")] == [10, 20]
    monkeypatch.delitem(settings._cache, "staff_roles")
    assert settings.get_roles(guild, "staff_roles") == []


def test_amorcage_env_des_listes_de_roles_resout_les_noms():
    from types import SimpleNamespace as N
    from utils import settings
    from utils.settings_registry import SETTINGS
    guild = N(roles=[N(id=7, name="Staff")])
    assert settings._env_to_value(SETTINGS["authorized_roles"], "Staff,5", guild) == "7,5"
