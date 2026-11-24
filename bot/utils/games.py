"""Jeux pilotés par ``site_games`` : validations et surcharges de forum (fonctions pures).

Utilisé par le cog ``GameManager`` (bot) et, à la tâche suivante, par l'API qui crée les jeux.
"""
import re

import discord

COMMAND_RE = r"^[a-z0-9_-]{1,32}$"
_COMMAND = re.compile(COMMAND_RE)

# Cooldown par défaut d'un ping de recherche de joueurs (colonne ``site_games.lfg_cooldown``).
DEFAULT_LFG_COOLDOWN = 3600

# Les six jeux d'avant ``site_games`` (ancien ``GAMES`` de ``cogs/fun/game_lfg.py``) : nom de
# leur forum existant, rattaché par nom au premier démarrage. Leur rôle porte le nom du jeu.
LEGACY_FORUM_NAMES: dict[str, str] = {
    "dbd": "dbd",
    "lol": "lol",
    "warframe": "warframe",
    "overwatch": "overwatch",
    "fortnite": "fortnite",
    "minecraft": "minecraft",
}


def forum_name(key: str) -> str:
    """Nom du forum d'un jeu : ancien nom pour les six jeux historiques, sinon sa clé."""
    return LEGACY_FORUM_NAMES.get(key, key)


# ── Nom de commande ──────────────────────────────────────────────────────────

def validate_command_name(name: str, taken: set[str]) -> str | None:
    """Message d'erreur en français, ou ``None`` si ``name`` est utilisable.

    ``taken`` : noms déjà pris (commandes des autres jeux et toutes les autres commandes du bot).
    """
    if not isinstance(name, str) or not _COMMAND.match(name):
        return ("Nom de commande invalide : 1 à 32 caractères parmi les minuscules, "
                "les chiffres, « _ » et « - ».")
    if name in taken:
        return f"La commande /{name} existe déjà."
    return None


# ── Emoji ────────────────────────────────────────────────────────────────────

_CUSTOM_EMOJI = re.compile(r"^<a?:[A-Za-z0-9_]{2,32}:\d{15,21}>$")

_VS16 = 0xFE0F
_ZWJ = 0x200D
_KEYCAP = 0x20E3
_SKIN_TONES = range(0x1F3FB, 0x1F400)
_REGIONAL = range(0x1F1E6, 0x1F200)
_TAGS = range(0xE0020, 0xE007F)
_TAG_END = 0xE007F

# Blocs de pictogrammes émoji (approximation suffisante : aucun texte ordinaire n'y figure).
_EMOJI_RANGES = (
    range(0x1F000, 0x1F1E6), range(0x1F200, 0x1F3FB), range(0x1F400, 0x1FB00),
    range(0x2190, 0x2200), range(0x2300, 0x2400), range(0x25A0, 0x2600),
    range(0x2600, 0x27C0), range(0x2900, 0x2980), range(0x2B00, 0x2C00),
)
_EMOJI_SINGLES = {0x00A9, 0x00AE, 0x203C, 0x2049, 0x2122, 0x2139, 0x24C2,
                  0x3030, 0x303D, 0x3297, 0x3299}


def _is_pictograph(cp: int) -> bool:
    return cp in _EMOJI_SINGLES or any(cp in r for r in _EMOJI_RANGES)


def _is_single_unicode_emoji(value: str) -> bool:
    """Un seul émoji : éventuellement modifié (VS16, teinte, étiquettes) ou joint par ZWJ."""
    cps = [ord(c) for c in value]
    if not cps:
        return False
    # Drapeau : exactement deux indicateurs régionaux.
    if all(cp in _REGIONAL for cp in cps):
        return len(cps) == 2
    # Touche : chiffre, # ou *, VS16 facultatif, puis U+20E3.
    if cps[-1] == _KEYCAP:
        body = cps[:-1]
        if body and body[-1] == _VS16:
            body = body[:-1]
        return len(body) == 1 and chr(body[0]) in "0123456789#*"
    # Séquence ZWJ : chaque élément est un pictogramme suivi de ses modificateurs.
    for segment in _split(cps, _ZWJ):
        if not segment or not _is_pictograph(segment[0]):
            return False
        rest = segment[1:]
        if rest and rest[0] == _VS16:
            rest = rest[1:]
        if rest and rest[0] in _SKIN_TONES:
            rest = rest[1:]
        if rest:  # séquence d'étiquettes (drapeaux de régions) terminée par U+E007F
            if rest[-1] != _TAG_END or not all(cp in _TAGS for cp in rest[:-1]):
                return False
    return True


def _split(cps: list[int], sep: int) -> list[list[int]]:
    parts, current = [], []
    for cp in cps:
        if cp == sep:
            parts.append(current)
            current = []
        else:
            current.append(cp)
    parts.append(current)
    return parts


def _emoji_key(value: str) -> str:
    """Forme de comparaison : ⚔ et ⚔️ (avec VS16) désignent le même émoji."""
    return value.replace(chr(_VS16), "")


def validate_emoji(value: str, taken: set[str]) -> str | None:
    """Message d'erreur en français, ou ``None`` si ``value`` est un seul émoji libre.

    Accepte un émoji Unicode ou un émoji personnalisé ``<:nom:id>`` (``<a:nom:id>`` animé).
    ``taken`` : émojis des autres jeux et des rôles de notification.
    """
    if not isinstance(value, str):
        return "Émoji invalide : un seul émoji attendu."
    value = value.strip()
    if not (_CUSTOM_EMOJI.match(value) or _is_single_unicode_emoji(value)):
        return "Émoji invalide : un seul émoji attendu (Unicode ou personnalisé <:nom:id>)."
    if _emoji_key(value) in {_emoji_key(t) for t in taken}:
        return f"L'émoji {value} est déjà utilisé."
    return None


# ── Surcharges de forum ──────────────────────────────────────────────────────

def forum_overwrites(everyone, game_role, staff_roles, bot_member, archived: bool) -> dict:
    """Surcharges du forum d'un jeu : réservé au rôle du jeu, au staff et au bot.

    Archivé : le rôle du jeu voit encore le forum mais n'écrit plus dans les fils.
    """
    overwrites: dict = {everyone: discord.PermissionOverwrite(view_channel=False)}
    if game_role is not None:
        if archived:
            overwrites[game_role] = discord.PermissionOverwrite(
                view_channel=True, send_messages=False, send_messages_in_threads=False,
                create_public_threads=False,
            )
        else:
            overwrites[game_role] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True, send_messages_in_threads=True,
            )
    for role in staff_roles or ():
        overwrites[role] = discord.PermissionOverwrite(
            view_channel=True, send_messages=True, send_messages_in_threads=True,
            manage_threads=True,
        )
    if bot_member is not None:
        overwrites[bot_member] = discord.PermissionOverwrite(
            view_channel=True, send_messages=True, send_messages_in_threads=True,
            create_public_threads=True, manage_threads=True, manage_messages=True,
            manage_channels=True, read_message_history=True, embed_links=True,
            attach_files=True, add_reactions=True,
        )
    return overwrites
