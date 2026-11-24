"""Données des jeux (étape 4, tâche 2) : colonnes de provisionnement, amorçage, réglage staff_roles.

Le SQL n'est pas exécuté (pas de PostgreSQL dans les tests) : on lit la migration et ``init.sql``
et on vérifie qu'ils posent les mêmes colonnes et le même amorçage que les jeux historiques du bot
(``bot/utils/games.py``).
"""
import ast
import re
from pathlib import Path

import pytest

from settings_registry import G_ROLES, SETTINGS, validate

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = (ROOT / "db/migrations/023_games_and_bump_rule.sql").read_text(encoding="utf-8")
INIT = (ROOT / "db/init.sql").read_text(encoding="utf-8")
EMOJIS = {"dbd": "🔪", "lol": "⚔️", "warframe": "🚀", "overwatch": "🌀", "fortnite": "🏹", "minecraft": "⛏️"}


def _bot_constant(name: str):
    """Constante littérale de ``bot/utils/games.py`` (lue par AST, sans importer le bot)."""
    tree = ast.parse((ROOT / "bot/utils/games.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        target = node.target if isinstance(node, ast.AnnAssign) else (
            node.targets[0] if isinstance(node, ast.Assign) else None)
        if getattr(target, "id", "") == name:
            return ast.literal_eval(node.value)
    raise AssertionError(f"{name} introuvable")


def _tail(sql: str) -> str:
    """Partie « bascule » : de l'UPDATE d'amorçage à la fin de l'instruction."""
    start = sql.index("UPDATE site_games g")
    return sql[start:sql.index(";", start) + 1]


@pytest.mark.parametrize("sql", [MIGRATION, INIT], ids=["migration", "init"])
class TestSchema:
    def test_colonnes(self, sql):
        for col in (
            "emoji        VARCHAR(32)",
            "command_name VARCHAR(32)",
            "lfg_cooldown INT NOT NULL DEFAULT 3600",
            "provisioned  BOOLEAN NOT NULL DEFAULT FALSE",
            "archived     BOOLEAN NOT NULL DEFAULT FALSE",
        ):
            assert f"ALTER TABLE site_games ADD COLUMN IF NOT EXISTS {col};" in sql

    def test_nom_de_commande_unique_et_idempotent(self, sql):
        assert "CREATE UNIQUE INDEX IF NOT EXISTS site_games_command_name_key ON site_games (command_name)" in sql

    def test_amorcage_des_six_jeux(self, sql):
        seed = _tail(sql)
        pairs = dict(re.findall(r"\('(\w+)', '([^']+)'\)", seed))
        assert pairs == EMOJIS
        assert "command_name = COALESCE(g.command_name, g.key)" in seed
        assert "emoji        = COALESCE(g.emoji, v.emoji)" in seed
        assert "provisioned  = TRUE" in seed

    def test_war_dogs_reste_non_provisionne(self, sql):
        seed = _tail(sql)
        assert "war-dogs" not in seed          # jamais touché : provisioned FALSE, command_name NULL
        assert "provisioned  = FALSE" not in seed  # la bascule ne dégrade jamais un jeu provisionné


def test_jeux_amorces_identiques_aux_jeux_historiques_du_bot():
    # GAMES (game_lfg.py) a disparu à la tâche 3 : les six jeux historiques sont ceux dont le
    # bot rattache le forum par nom au premier démarrage.
    assert set(_bot_constant("LEGACY_FORUM_NAMES")) == set(EMOJIS)


def test_cooldown_par_defaut_est_celui_du_bot():
    assert _bot_constant("DEFAULT_LFG_COOLDOWN") == 3600
    assert "lfg_cooldown INT NOT NULL DEFAULT 3600" in MIGRATION


# ── staff_roles ──────────────────────────────────────────────────────────────

def test_staff_roles_est_un_reglage_de_roles_reserve_admin():
    from routes.settings import ADMIN_ONLY_SETTINGS
    assert SETTINGS["staff_roles"].group == G_ROLES
    assert "staff_roles" in ADMIN_ONLY_SETTINGS


def test_staff_roles_valide_une_liste_d_identifiants():
    assert validate("staff_roles", "1, 2 ,3") == "1,2,3"
    assert validate("staff_roles", "") == ""
    with pytest.raises(ValueError):
        validate("staff_roles", "1,abc")


def test_staff_roles_refuse_settings_manage_seul(client, fake_db, session_with):
    session_with({"settings.manage"})
    r = client.put("/admin/settings/staff_roles", json={"value": "123"})
    assert r.status_code == 403


def test_staff_roles_accepte_un_admin(client, fake_db, session_with, monkeypatch):
    import bot_client

    async def fake_post(path, json=None, timeout=1.5):
        return {"ok": True}

    monkeypatch.setattr(bot_client, "bot_post", fake_post)
    session_with((), is_admin=True)
    r = client.put("/admin/settings/staff_roles", json={"value": "1,2"})
    assert r.status_code == 200
