"""
Discord role resolution via bot token.
Auth (session management, OAuth2) is now handled by BetterAuth in the Next.js web service.
web-api validates sessions by reading the BetterAuth session table directly via auth_middleware.py.
"""
import os

DISCORD_API         = "https://discord.com/api/v10"
DISCORD_TOKEN       = os.getenv("DISCORD_TOKEN", "")
GUILD_ID            = int(os.getenv("GUILD_ID", "0"))
ADMIN_ROLE_NAME     = os.getenv("ADMIN_ROLE_NAME", "Administration")
REDACTEUR_ROLE_NAME = os.getenv("REDACTEUR_ROLE_NAME", "rédacteur")
