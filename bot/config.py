import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN          = os.getenv('DISCORD_TOKEN')
GUILD_ID               = os.getenv('GUILD_ID')
BLAGUES_API_TOKEN      = os.getenv('BLAGUES_API_TOKEN')
TOKEN_BLAGUE_API       = BLAGUES_API_TOKEN

BOT_CHANNEL_START      = os.getenv('BOT_CHANNEL_START')
LOG_CHANNEL_ID         = int(os.getenv('LOG_CHANNEL_ID', '0') or '0') or None
VOICE_LOG_CHANNEL_ID   = int(os.getenv('VOICE_LOG_CHANNEL_ID', '0') or '0') or None
CONFESSION_CHANNEL_ID  = int(os.getenv('CONFESSION_CHANNEL_ID', '0') or '0') or None
ANIME_NEWS_CHANNEL_ID  = os.getenv('ANIME_NEWS_CHANNEL_ID')
WELCOME_CHANNEL_ID     = int(os.getenv('WELCOME_CHANNEL_ID', '0') or '0') or None
MEMBER_LOGS_CHANNEL_ID = os.getenv('MEMBER_LOGS_CHANNEL_ID')

ADMIN_ROLE_NAME      = os.getenv('ADMIN_ROLE_NAME', 'Administration')
REDACTEUR_ROLE_NAME  = os.getenv('REDACTEUR_ROLE_NAME', 'rédacteur')
AUTHORIZED_ROLES     = [r.strip() for r in os.getenv('AUTHORIZED_ROLES', '').split(',') if r.strip()]
ROLE_BATMAN          = os.getenv('ROLE_BATMAN', '')
VOICE_HOURS_FOR_ROLE = int(os.getenv('VOICE_HOURS_FOR_ROLE', '100'))

ANIME_THUMBNAIL_URL    = os.getenv('ANIME_THUMBNAIL_URL', '')
ANIME_AUTHOR_AVATAR_URL = os.getenv('ANIME_AUTHOR_AVATAR_URL', '')
DISCORD_WEBHOOK_URL    = os.getenv('DISCORD_WEBHOOK_URL', '')

BOT_API_TOKEN = os.getenv('BOT_API_TOKEN', '')
BOT_API_PORT  = int(os.getenv('BOT_API_PORT', '8001'))


ACHIEVEMENTS_CHANNEL_ID = int(os.getenv('ACHIEVEMENTS_CHANNEL_ID', '0') or '0') or None
XP_LEVEL_ROLES: dict = {}  # dict level -> role_name, configurable depuis .env


def validate_config():
    required = {
        'DISCORD_TOKEN': DISCORD_TOKEN,
        'GUILD_ID': GUILD_ID,
        'BOT_CHANNEL_START': BOT_CHANNEL_START,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        raise ValueError(f"Variables d'environnement manquantes: {', '.join(missing)}")
    try:
        int(GUILD_ID)
        int(BOT_CHANNEL_START)
    except ValueError:
        raise ValueError("GUILD_ID et BOT_CHANNEL_START doivent être des entiers")
