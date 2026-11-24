"""Jeux (étape 4, tâche 3) : validations de nom de commande et d'émoji, surcharges de forum."""
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.games import (  # noqa: E402
    COMMAND_RE, LEGACY_FORUM_NAMES, forum_name, forum_overwrites,
    validate_command_name, validate_emoji,
)

NOTIFICATIONS = {"⭐", "📺", "🎭"}


# ── Nom de commande ──────────────────────────────────────────────────────────

def test_command_re_est_celui_du_plan():
    assert COMMAND_RE == r"^[a-z0-9_-]{1,32}$"


@pytest.mark.parametrize("name", ["dbd", "war-dogs", "jeu_2", "a", "x" * 32])
def test_nom_de_commande_valide(name):
    assert validate_command_name(name, set()) is None


@pytest.mark.parametrize("name", ["", "Dbd", "war dogs", "x" * 33, "jeu!", "é", None, "dbd\n"])
def test_nom_de_commande_mal_forme(name):
    error = validate_command_name(name, set())
    assert error and "invalide" in error


def test_nom_deja_pris_par_un_autre_jeu():
    assert validate_command_name("dbd", {"dbd", "lol"}) == "La commande /dbd existe déjà."


@pytest.mark.parametrize("name", ["rang", "blague"])
def test_nom_egal_a_une_commande_existante_du_bot(name):
    # L'appelant passe dans ``taken`` les commandes du bot (GameManager.taken_command_names).
    assert validate_command_name(name, {"rang", "blague", "dbd"}) == f"La commande /{name} existe déjà."


# ── Émoji ────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("value", [
    "🔪", "⚔️", "🚀", "🌀", "🏹", "⛏️",          # les six jeux historiques
    "⚔",                                          # sans VS16
    "👍🏽",                                         # teinte
    "🧑‍🚀",                                         # séquence ZWJ
    "🇫🇷",                                         # drapeau
    "3️⃣",                                         # touche
    "🏴󠁧󠁢󠁳󠁣󠁴󠁿",                                         # drapeau à étiquettes (Écosse)
    "<:saucisse:123456789012345678>",
    "<a:danse:123456789012345678>",
])
def test_emoji_valide(value):
    assert validate_emoji(value, NOTIFICATIONS) is None


@pytest.mark.parametrize("value", [
    "", "a", "dbd", ":fire:", "🔪🔪", "🔪 ⚔️", "🔪a", "🇫🇷🇫🇷", "<:x:12>", "<saucisse:123456789012345678>", None,
])
def test_emoji_invalide(value):
    error = validate_emoji(value, NOTIFICATIONS)
    assert error and "invalide" in error


def test_emoji_deja_pris_par_un_jeu():
    assert validate_emoji("🔪", {"🔪"} | NOTIFICATIONS) == "L'émoji 🔪 est déjà utilisé."


def test_emoji_deja_pris_avec_ou_sans_vs16():
    assert validate_emoji("⚔", {"⚔️"}) == "L'émoji ⚔ est déjà utilisé."
    assert validate_emoji("⚔️", {"⚔"}) == "L'émoji ⚔️ est déjà utilisé."


@pytest.mark.parametrize("value", sorted(NOTIFICATIONS))
def test_emoji_deja_pris_par_un_role_de_notification(value):
    assert validate_emoji(value, NOTIFICATIONS) == f"L'émoji {value} est déjà utilisé."


# ── Forums historiques ───────────────────────────────────────────────────────

def test_forums_historiques_et_nom_par_defaut():
    assert LEGACY_FORUM_NAMES == {k: k for k in ("dbd", "lol", "warframe", "overwatch", "fortnite", "minecraft")}
    assert forum_name("dbd") == "dbd"
    assert forum_name("war-dogs") == "war-dogs"
    assert all(re.match(COMMAND_RE, k) for k in LEGACY_FORUM_NAMES)


# ── Surcharges ───────────────────────────────────────────────────────────────

EVERYONE, GAME, STAFF1, STAFF2, BOT = "everyone", "jeu", "staff1", "staff2", "bot"


def _allowed(ow):
    """Permissions accordées et refusées par la surcharge (``None`` = héritée)."""
    alias = {"read_messages": "view_channel"}  # discord.py stocke view_channel sous ce nom
    allow = {alias.get(name, name) for name, v in ow if v is True}
    deny = {alias.get(name, name) for name, v in ow if v is False}
    return allow, deny


def test_surcharges_jeu_actif():
    ows = forum_overwrites(EVERYONE, GAME, [STAFF1, STAFF2], BOT, archived=False)
    assert set(ows) == {EVERYONE, GAME, STAFF1, STAFF2, BOT}

    allow, deny = _allowed(ows[EVERYONE])
    assert (allow, deny) == (set(), {"view_channel"})

    allow, deny = _allowed(ows[GAME])
    assert {"view_channel", "send_messages", "send_messages_in_threads"} <= allow and not deny

    for staff in (STAFF1, STAFF2):
        allow, _ = _allowed(ows[staff])
        assert {"view_channel", "manage_threads", "send_messages_in_threads"} <= allow

    allow, deny = _allowed(ows[BOT])
    assert {"view_channel", "send_messages", "send_messages_in_threads", "manage_threads",
            "manage_messages", "manage_channels"} <= allow and not deny


def test_surcharges_jeu_archive():
    ows = forum_overwrites(EVERYONE, GAME, [STAFF1], BOT, archived=True)
    allow, deny = _allowed(ows[GAME])
    # Archivé : forum masqué au rôle du jeu.
    assert allow == set() and "view_channel" in deny
    # Le staff et le bot gardent la main sur un forum archivé.
    assert {"view_channel", "manage_threads"} <= _allowed(ows[STAFF1])[0]
    assert "send_messages_in_threads" in _allowed(ows[BOT])[0]
    assert _allowed(ows[EVERYONE])[1] == {"view_channel"}


def test_surcharges_sans_role_ni_staff_ni_bot():
    ows = forum_overwrites(EVERYONE, None, [], None, archived=False)
    assert list(ows) == [EVERYONE]


def test_dangerous_permissions_pure():
    import discord
    from utils.games import has_dangerous_permissions
    assert not has_dangerous_permissions(discord.Permissions(6479531585))
    assert not has_dangerous_permissions(discord.Permissions(0))
    for name in ("administrator", "manage_roles", "mention_everyone", "view_guild_insights",
                 "moderate_members", "manage_webhooks"):
        assert has_dangerous_permissions(discord.Permissions(**{name: True})), name
