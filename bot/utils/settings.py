"""Réglages du serveur : cache mémoire alimenté par la table ``bot_settings``.

Ne dépend pas de ``config``. Le cache est rechargé sur ``POST /settings/reload``
(modification depuis le site) et toutes les 5 minutes.
"""
import asyncio
import logging
import os
from typing import Optional

import discord
from discord.ext import tasks

from utils.role_ref import role_ref
from utils.settings_backoff import CreationBackoff
from utils.settings_registry import ROLE_LIST_KEYS, SETTINGS, needs_channel_creation

logger = logging.getLogger(__name__)

_cache: dict[str, str] = {}

# Posé par main.on_ready une fois le premier load() tenté (réussi ou non) : les
# tâches de démarrage des cogs l'attendent avant de lire un réglage.
ready = asyncio.Event()

# Créations de salon refusées par Discord (403) : pas de nouvel essai avant 10 min
# ni avant le prochain load().
_creation_backoff = CreationBackoff()


def _db():
    # Import tardif : le pool n'existe qu'après init_database().
    from utils.database import db_manager
    return db_manager


# ── Lecture ───────────────────────────────────────────────────────────────────

def get(key: str) -> Optional[str]:
    """Valeur enregistrée, sinon valeur par défaut du registre, sinon ``None``."""
    value = _cache.get(key)
    if value:
        return value
    definition = SETTINGS.get(key)
    return definition.default if definition and definition.default else None


def get_int(key: str, default: Optional[int] = None) -> Optional[int]:
    value = get(key)
    if value is not None and value.strip().isdigit():
        return int(value)
    return default


# (clé, valeur) déjà signalées : get_role est appelé à chaque vérification de commande,
# l'avertissement n'est écrit qu'une fois par valeur (une nouvelle valeur réarme le signal).
_warned: set[tuple[str, str]] = set()


def _warn_once(key: str, stored: str, message: str, *args) -> None:
    if (key, stored) in _warned:
        return
    _warned.add((key, stored))
    logger.warning(message, *args)


def get_role(guild: discord.Guild, key: str) -> Optional[discord.Role]:
    """Rôle réglé, par identifiant seulement ; repli sur le nom du registre si la ligne est absente.

    Un réglage renseigné qui ne résout plus (rôle supprimé ou recréé) donne ``None`` :
    aucun rôle homonyme ne reprend ses droits (règle de ``utils.role_ref``).
    """
    definition = SETTINGS.get(key)
    stored = _cache.get(key)
    ref = role_ref(stored, definition.default if definition else None)
    if ref is None:
        if stored:
            _warn_once(key, stored, "Réglage %s invalide (%r) : aucun rôle retenu", key, stored)
        return None
    kind, target = ref
    if kind == "id":
        role = guild.get_role(target)
        if role is None and stored:
            _warn_once(key, stored, "Réglage %s : le rôle %s n'existe plus, aucun rôle retenu", key, target)
        return role
    return discord.utils.get(guild.roles, name=target)


def get_roles(guild: discord.Guild, key: str) -> list[discord.Role]:
    """Rôles d'un réglage « liste de rôles » (identifiants séparés par des virgules).

    Seuls les identifiants qui résolvent encore sont renvoyés ; les autres sont ignorés
    (un rôle supprimé ne retombe jamais sur un homonyme).
    """
    roles: list[discord.Role] = []
    for part in (get(key) or "").split(","):
        part = part.strip()
        if not part.isdigit():
            continue
        role = guild.get_role(int(part))
        if role is not None and role not in roles:
            roles.append(role)
    return roles


# ── Chargement ────────────────────────────────────────────────────────────────

async def load() -> None:
    rows = await _db().fetch("SELECT key, value FROM bot_settings")
    _cache.clear()
    _cache.update({r["key"]: r["value"] for r in rows if r["value"]})
    _creation_backoff.clear()
    logger.info("%d réglages chargés", len(_cache))


@tasks.loop(minutes=5)
async def _refresh():
    try:
        await load()
    except Exception as e:
        logger.warning("Rechargement des réglages impossible : %s", e)


def start_refresh() -> None:
    if not _refresh.is_running():
        _refresh.start()


async def seed_from_env(guild: Optional[discord.Guild] = None) -> None:
    """Copie en base les réglages présents dans l'environnement mais absents de la base.

    Préserve la configuration actuelle au premier démarrage. Les rôles réglés par
    nom (``ADMIN_ROLE_NAME``, ``AUTHORIZED_ROLES``, ...) sont convertis en identifiants
    quand ``guild`` est fourni ; un nom introuvable est ignoré.
    """
    db = _db()
    existing = {r["key"] for r in await db.fetch("SELECT key FROM bot_settings")}
    for definition in SETTINGS.values():
        if definition.key in existing or not definition.env:
            continue
        raw = (os.getenv(definition.env) or "").strip()
        if not raw:
            continue
        value = _env_to_value(definition, raw, guild)
        if not value:
            continue
        await db.execute(
            "INSERT INTO bot_settings (key, value) VALUES ($1, $2) ON CONFLICT (key) DO NOTHING",
            definition.key, value,
        )


def _role_id(guild: Optional[discord.Guild], name_or_id: str) -> Optional[str]:
    if name_or_id.isdigit():
        return name_or_id
    if guild is None:
        return None
    role = discord.utils.get(guild.roles, name=name_or_id)
    return str(role.id) if role else None


def _env_to_value(definition, raw: str, guild: Optional[discord.Guild]) -> Optional[str]:
    if definition.kind == "role":
        return _role_id(guild, raw)
    if definition.key in ROLE_LIST_KEYS:
        ids = [_role_id(guild, part.strip()) for part in raw.split(",") if part.strip()]
        return ",".join(i for i in ids if i) or None
    if definition.kind in ("channel", "category") and not raw.isdigit():
        return None
    return raw


# ── Création de salon ─────────────────────────────────────────────────────────

_channel_locks: dict[str, asyncio.Lock] = {}


async def ensure_channel(guild: discord.Guild, key: str) -> discord.abc.GuildChannel:
    """Renvoie le salon réglé ; le crée (nom et type du registre) s'il manque."""
    definition = SETTINGS.get(key)
    if definition is None or not definition.channel_name:
        raise ValueError(f"{key} n'est pas un salon créable")

    # Verrou par clé : deux événements simultanés ne créent pas deux salons.
    async with _channel_locks.setdefault(key, asyncio.Lock()):
        stored = get(key)
        existing = {c.id for c in guild.channels}
        if not needs_channel_creation(stored, existing):
            return guild.get_channel(int(stored))

        kind = definition.channel_type or "text"
        reason = "Salon créé par Hermes (réglage manquant)"
        if kind == "category":
            channel = await guild.create_category(definition.channel_name, reason=reason)
        elif kind == "forum":
            channel = await guild.create_forum(definition.channel_name, reason=reason)
        else:
            channel = await guild.create_text_channel(definition.channel_name, reason=reason)

        # Cache d'abord : si l'écriture en base échoue, le salon n'est pas recréé
        # à chaque événement jusqu'au redémarrage.
        _cache[key] = str(channel.id)
        await _db().execute(
            """INSERT INTO bot_settings (key, value, updated_at) VALUES ($1, $2, NOW())
               ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()""",
            key, str(channel.id),
        )
    logger.info("Salon %s créé pour le réglage %s", channel.id, key)
    await _announce_creation(guild, definition, channel)
    return channel


async def configured_channel(guild: Optional[discord.Guild], key: str):
    """Salon réglé, recréé par ``ensure_channel`` s'il a été supprimé.

    ``None`` si le réglage est vide (fonction désactivée, comme avant avec une
    variable d'environnement absente) ou si Discord refuse la création. Ne lève
    jamais : appelé depuis des journaux et des listeners.
    """
    if guild is None or not get(key):
        return None
    if _creation_backoff.is_blocked(key):
        # Création refusée récemment : on ne renvoie que le salon s'il existe.
        return _cached_channel(guild, key)
    try:
        return await ensure_channel(guild, key)
    except discord.Forbidden as e:
        _creation_backoff.block(key)
        logger.warning("Création du salon %s refusée, nouvel essai dans 10 min : %s", key, e)
        return None
    except discord.HTTPException as e:
        logger.warning("Salon du réglage %s indisponible : %s", key, e)
        return None
    except Exception:
        # Erreur de base après la création (pool absent, asyncpg…) : le cache pointe
        # déjà sur le nouveau salon, on le renvoie.
        logger.error("Enregistrement du salon %s impossible", key, exc_info=True)
        return _cached_channel(guild, key)


def _cached_channel(guild: discord.Guild, key: str):
    stored = get(key)
    if stored and stored.isdigit():
        return guild.get_channel(int(stored))
    return None


async def _announce_creation(guild: discord.Guild, definition, channel) -> None:
    """Signale la création dans le journal d'administration (best effort)."""
    log_id = get_int("admin_log_channel")
    if not log_id or log_id == channel.id:
        return
    log_channel = guild.get_channel(log_id)
    if log_channel is None:
        return
    try:
        await log_channel.send(
            f"🆕 Salon {channel.mention} créé par Hermes pour le réglage « {definition.label} »."
        )
    except discord.HTTPException as e:
        logger.warning("Annonce de création impossible : %s", e)
