"""
Discord role resolution via bot token.
Auth (session management, OAuth2) is now handled by BetterAuth in the Next.js web service.
web-api validates sessions by reading the BetterAuth session table directly via auth_middleware.py.

Rôles admin/rédacteur : réglages ``admin_role``/``redacteur_role`` de ``bot_settings``
(identifiants), lus à l'usage ; repli sur ``ADMIN_ROLE_NAME``/``REDACTEUR_ROLE_NAME``
(noms) tant que la ligne est absente.
"""
import os

import database as db

DISCORD_API         = "https://discord.com/api/v10"
DISCORD_TOKEN       = os.getenv("DISCORD_TOKEN", "")
GUILD_ID            = int(os.getenv("GUILD_ID", "0"))

# rôle -> (clé du réglage, variable d'environnement de repli, nom par défaut)
_STAFF_ROLES = {
    "admin":     ("admin_role", "ADMIN_ROLE_NAME", "Administration"),
    "redacteur": ("redacteur_role", "REDACTEUR_ROLE_NAME", "rédacteur"),
}


async def staff_role_refs() -> dict[str, dict]:
    """``{"admin": {"id": "…"} | {"name": "…"}, "redacteur": …}``."""
    keys = [key for key, _, _ in _STAFF_ROLES.values()]
    rows = await db.fetch(
        "SELECT key, value FROM bot_settings WHERE key = ANY($1::text[])", keys
    )
    stored = {r["key"]: r["value"] for r in rows if r["value"]}
    refs = {}
    for label, (key, env, default) in _STAFF_ROLES.items():
        if key in stored:
            refs[label] = {"id": stored[key]}
        else:
            refs[label] = {"name": os.getenv(env) or default}
    return refs


def member_has_role(ref: dict, member_role_ids: list[str], guild_roles: dict[str, str]) -> bool:
    """Le membre porte-t-il le rôle ``ref`` ? ``guild_roles`` : identifiant -> nom."""
    if "id" in ref:
        return ref["id"] in member_role_ids
    return any(guild_roles.get(role_id) == ref["name"] for role_id in member_role_ids)
