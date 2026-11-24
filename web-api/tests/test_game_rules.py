"""Validations des jeux côté web-api (étape 4, tâche 4) : copie identique de ``bot/utils/games.py``.

1. La source des fonctions recopiées est identique à celle du bot (lecture AST, sans importer
   discord.py) : une correction d'un côté qui oublie l'autre fait échouer ce test.
2. Les mêmes cas que ``bot/tests/test_games_pure.py`` passent sur la copie.
"""
import ast
from pathlib import Path

import pytest

import game_rules
from game_rules import COMMAND_RE, NOTIFICATION_EMOJIS, validate_command_name, validate_emoji

ROOT = Path(__file__).resolve().parents[2]
BOT_GAMES = ROOT / "bot/utils/games.py"
WEB_GAMES = Path(game_rules.__file__)
NOTIFICATIONS = set(NOTIFICATION_EMOJIS)


def _definitions(path: Path) -> dict[str, str]:
    """Source normalisée (``ast.dump``) de chaque fonction et constante de premier niveau."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out[node.name] = ast.dump(node)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            target = node.target if isinstance(node, ast.AnnAssign) else node.targets[0]
            if isinstance(target, ast.Name):
                out[target.id] = ast.dump(node)
    return out


def test_copie_identique_au_bot():
    bot, web = _definitions(BOT_GAMES), _definitions(WEB_GAMES)
    copied = set(web) - {"NOTIFICATION_EMOJIS"}
    assert {"validate_command_name", "validate_emoji", "_is_single_unicode_emoji", "COMMAND_RE",
            "_CUSTOM_EMOJI", "_EMOJI_RANGES"} <= copied
    for name in sorted(copied):
        assert name in bot, f"{name} absent de bot/utils/games.py"
        assert web[name] == bot[name], f"{name} diffère de bot/utils/games.py"


def test_emojis_de_notification_identiques_au_bot():
    tree = ast.parse((ROOT / "bot/cogs/system/reaction_roles.py").read_text(encoding="utf-8"))
    node = next(n for n in tree.body if isinstance(n, ast.AnnAssign)
                and getattr(n.target, "id", "") == "NOTIFICATION_ROLES")
    assert tuple(ast.literal_eval(node.value)) == NOTIFICATION_EMOJIS


def test_command_re_est_celui_du_plan():
    assert COMMAND_RE == r"^[a-z0-9_-]{1,32}$"


@pytest.mark.parametrize("name", ["dbd", "war-dogs", "jeu_2", "a", "x" * 32])
def test_nom_de_commande_valide(name):
    assert validate_command_name(name, set()) is None


@pytest.mark.parametrize("name", ["", "Dbd", "war dogs", "x" * 33, "jeu!", "é", None, "dbd\n", 3])
def test_nom_de_commande_mal_forme(name):
    error = validate_command_name(name, set())
    assert error and "invalide" in error


@pytest.mark.parametrize("name", ["rang", "blague", "dbd"])
def test_nom_deja_pris(name):
    assert validate_command_name(name, {"rang", "blague", "dbd"}) == f"La commande /{name} existe déjà."


@pytest.mark.parametrize("value", ["🔪", "⚔️", "⚔", "👍🏽", "🧑‍🚀", "🇫🇷", "3️⃣", "<:saucisse:123456789012345678>"])
def test_emoji_valide(value):
    assert validate_emoji(value, NOTIFICATIONS) is None


@pytest.mark.parametrize("value", ["", "a", "dbd", ":fire:", "🔪🔪", "🔪 ⚔️", "🔪a", "<:x:12>", None])
def test_emoji_invalide(value):
    error = validate_emoji(value, NOTIFICATIONS)
    assert error and "invalide" in error


@pytest.mark.parametrize("value", ["⭐", "📺", "🎭"])
def test_emoji_pris_par_une_notification(value):
    assert validate_emoji(value, NOTIFICATIONS) == f"L'émoji {value} est déjà utilisé."


def test_emoji_pris_avec_ou_sans_vs16():
    assert validate_emoji("⚔", {"⚔️"}) == "L'émoji ⚔ est déjà utilisé."
