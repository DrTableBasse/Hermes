"""Secrets et infrastructure uniquement.

Les réglages du serveur (salons, rôles, seuils, URL) sont en base : voir
``utils/settings.py`` et ``utils/settings_registry.py``.
"""
import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN          = os.getenv('DISCORD_TOKEN')
GUILD_ID               = os.getenv('GUILD_ID')
BLAGUES_API_TOKEN      = os.getenv('BLAGUES_API_TOKEN')
TOKEN_BLAGUE_API       = BLAGUES_API_TOKEN
DISCORD_WEBHOOK_URL    = os.getenv('DISCORD_WEBHOOK_URL', '')

BOT_API_TOKEN = os.getenv('BOT_API_TOKEN', '')
BOT_API_PORT  = int(os.getenv('BOT_API_PORT', '8001'))


def validate_config():
    required = {
        'DISCORD_TOKEN': DISCORD_TOKEN,
        'GUILD_ID': GUILD_ID,
        # L'API interne (kick/ban/warn) refuse de tourner sans jeton.
        'BOT_API_TOKEN': BOT_API_TOKEN,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        raise ValueError(f"Variables d'environnement manquantes: {', '.join(missing)}")
    try:
        int(GUILD_ID)
    except ValueError:
        raise ValueError("GUILD_ID doit être un entier")
