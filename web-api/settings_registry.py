"""Registre des réglages du serveur (module pur, sans discord ni config).

Copié à l'identique dans ``web-api/settings_registry.py`` : un test du bot vérifie
que les deux fichiers sont identiques. Toute modification se fait des deux côtés.
"""
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

KINDS = ("channel", "category", "role", "int", "text", "url", "bool")
ID_KINDS = ("channel", "category", "role")


@dataclass(frozen=True)
class SettingDef:
    key: str
    label: str
    group: str
    kind: str
    default: Optional[str] = None
    env: Optional[str] = None            # ancien nom de variable d'environnement (amorçage)
    channel_name: Optional[str] = None   # nom du salon créé par Hermes s'il manque
    channel_type: Optional[str] = None   # "text" | "forum" | "category"
    public: bool = False                 # exposé sans connexion par GET /settings/public


def _s(key, label, group, kind, default=None, env=None, channel_name=None,
       channel_type=None, public=False) -> SettingDef:
    return SettingDef(key, label, group, kind, default, env, channel_name, channel_type, public)


G_CHANNELS = "Salons"
G_LOGS = "Journaux"
G_ROLES = "Rôles"
G_XP = "Niveaux et vocal"
G_BUMP = "Bump"
G_ANIME = "Anime"
G_SITE = "Site"

_DEFS = [
    # Salons
    _s("welcome_channel", "Salon d'accueil", G_CHANNELS, "channel", env="WELCOME_CHANNEL_ID",
       channel_name="accueil", channel_type="text"),
    _s("bot_start_channel", "Salon du message de démarrage", G_CHANNELS, "channel",
       env="BOT_CHANNEL_START", channel_name="hermes", channel_type="text"),
    _s("achievements_channel", "Salon des succès", G_CHANNELS, "channel",
       env="ACHIEVEMENTS_CHANNEL_ID", channel_name="succes", channel_type="text"),
    _s("confession_channel", "Salon des confessions", G_CHANNELS, "channel",
       env="CONFESSION_CHANNEL_ID", channel_name="confessions", channel_type="text"),
    _s("anime_news_channel", "Salon des actualités anime", G_CHANNELS, "channel",
       env="ANIME_NEWS_CHANNEL_ID", channel_name="anime-news", channel_type="text"),
    _s("reaction_role_channel", "Salon des rôles à réaction", G_CHANNELS, "channel",
       default="836712775194771486", env="REACTION_ROLE_CHANNEL_ID",
       channel_name="roles", channel_type="text"),
    _s("gallery_channel", "Salon de la galerie", G_CHANNELS, "channel",
       channel_name="galerie", channel_type="text"),
    _s("ticket_panel_channel", "Salon du panneau de tickets", G_CHANNELS, "channel",
       channel_name="tickets", channel_type="text", public=True),
    _s("game_forums_category", "Catégorie des forums de jeux", G_CHANNELS, "category",
       env="GAME_FORUMS_CATEGORY_ID", channel_name="Jeux", channel_type="category"),
    _s("ticket_category", "Catégorie des tickets", G_CHANNELS, "category",
       env="TICKET_CATEGORY_ID", channel_name="Tickets", channel_type="category"),
    # Journaux
    _s("log_channel", "Journal général", G_LOGS, "channel", env="LOG_CHANNEL_ID",
       channel_name="all-logs", channel_type="text"),
    _s("voice_log_channel", "Journal vocal", G_LOGS, "channel", env="VOICE_LOG_CHANNEL_ID",
       channel_name="logs-vocal", channel_type="text"),
    _s("message_log_channel", "Journal des messages", G_LOGS, "channel",
       default="777133504634945627", env="MESSAGE_LOG_CHANNEL_ID",
       channel_name="logs-messages", channel_type="text"),
    _s("member_logs_channel", "Journal des membres", G_LOGS, "channel",
       env="MEMBER_LOGS_CHANNEL_ID", channel_name="logs-membres", channel_type="text"),
    _s("admin_log_channel", "Journal d'administration", G_LOGS, "channel",
       env="ADMIN_LOG_CHANNEL_ID", channel_name="logs-admin", channel_type="text"),
    _s("bump_channel", "Salon du bump", G_BUMP, "channel", default="1068608173310754886",
       env="BUMP_CHANNEL_ID", channel_name="bump", channel_type="text"),
    _s("bump_log_channel", "Journal du bump", G_BUMP, "channel", default="777124592552116234",
       env="BUMP_LOG_CHANNEL_ID", channel_name="logs-bump", channel_type="text"),
    # Rôles (stockés par identifiant ; les anciens noms sont résolus à l'amorçage)
    _s("admin_role", "Rôle administration", G_ROLES, "role", default="Administration",
       env="ADMIN_ROLE_NAME"),
    _s("redacteur_role", "Rôle rédacteur", G_ROLES, "role", default="rédacteur",
       env="REDACTEUR_ROLE_NAME"),
    _s("mod_role", "Rôle modération", G_ROLES, "role", default="Modération"),
    _s("authorized_roles", "Rôles autorisés (identifiants séparés par des virgules)",
       G_ROLES, "text", env="AUTHORIZED_ROLES"),
    _s("staff_roles", "Rôles du staff (identifiants séparés par des virgules)",
       G_ROLES, "text"),
    _s("role_batman", "Rôle Batman", G_ROLES, "role", env="ROLE_BATMAN"),
    _s("role_level_5", "Rôle du niveau 5", G_XP, "role", env="ROLE_LEVEL_5"),
    _s("role_level_10", "Rôle du niveau 10", G_XP, "role", env="ROLE_LEVEL_10"),
    _s("role_level_20", "Rôle du niveau 20", G_XP, "role", env="ROLE_LEVEL_20"),
    _s("role_level_50", "Rôle du niveau 50", G_XP, "role", env="ROLE_LEVEL_50"),
    _s("voice_hours_for_role", "Heures de vocal pour le rôle", G_XP, "int",
       default="100", env="VOICE_HOURS_FOR_ROLE"),
    _s("bump_role", "Rôle des bumpers", G_BUMP, "role", default="Bumper Fou",
       env="BUMP_ROLE_NAME"),
    _s("bump_role_threshold", "Bumps requis pour le rôle", G_BUMP, "int", default="20",
       env="BUMP_ROLE_THRESHOLD"),
    _s("bump_reminder_delay_minutes", "Délai du rappel de bump (minutes)", G_BUMP, "int",
       default="120", env="BUMP_REMINDER_DELAY_MINUTES"),
    _s("anime_thumbnail_url", "Vignette des actualités anime", G_ANIME, "url",
       env="ANIME_THUMBNAIL_URL"),
    _s("anime_author_avatar_url", "Avatar d'auteur des actualités anime", G_ANIME, "url",
       env="ANIME_AUTHOR_AVATAR_URL"),
    _s("invite_url", "Lien d'invitation Discord", G_SITE, "url",
       env="NEXT_PUBLIC_DISCORD_INVITE_URL", public=True),
]

SETTINGS: dict[str, SettingDef] = {d.key: d for d in _DEFS}

# Réglages de type texte qui contiennent une liste d'identifiants de rôles séparés par des virgules.
ROLE_LIST_KEYS = frozenset({"authorized_roles", "staff_roles"})


def _check_id(raw: str) -> str:
    if not raw.isascii() or not raw.isdigit():
        raise ValueError("identifiant Discord numérique attendu")
    return raw


def validate(key: str, raw: str) -> str:
    """Valide ``raw`` pour ``key`` et renvoie la valeur normalisée.

    Lève ``ValueError`` : clé inconnue, entier invalide, URL non http(s),
    identifiant non numérique. Une valeur vide efface le réglage.
    """
    definition = SETTINGS.get(key)
    if definition is None:
        raise ValueError(f"réglage inconnu : {key}")
    value = (raw or "").strip()
    if value == "":
        return ""
    kind = definition.kind
    if kind in ID_KINDS:
        return _check_id(value)
    if kind == "int":
        if not value.isascii() or not value.isdigit():
            raise ValueError("entier positif attendu")
        return str(int(value))
    if kind == "url":
        parsed = urlparse(value)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError("URL http(s) attendue")
        return value
    if kind == "bool":
        if value.lower() not in ("true", "false"):
            raise ValueError("booléen attendu (true/false)")
        return value.lower()
    if key in ROLE_LIST_KEYS:
        parts = [p.strip() for p in value.split(",") if p.strip()]
        return ",".join(_check_id(p) for p in parts)
    return value


def needs_channel_creation(stored_id: Optional[str], existing_ids: set[int]) -> bool:
    """Vrai si le salon réglé est absent (jamais défini, invalide ou supprimé)."""
    if stored_id is None or not str(stored_id).strip().isdigit():
        return True
    return int(stored_id) not in existing_ids
