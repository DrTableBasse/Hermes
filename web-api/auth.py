"""
Auth via Authentik OIDC.
Flow: Hermes → Authentik → Discord → Authentik → Hermes
Roles are checked directly via the Discord bot token (no guilds.members.read needed from the user).
"""
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from jose import JWTError, jwt

DISCORD_API        = "https://discord.com/api/v10"
DISCORD_TOKEN      = os.getenv('DISCORD_TOKEN', '')      # bot token for guild lookups
GUILD_ID           = int(os.getenv('GUILD_ID', '0'))
ADMIN_ROLE_NAME    = os.getenv('ADMIN_ROLE_NAME', 'Administration')
REDACTEUR_ROLE_NAME = os.getenv('REDACTEUR_ROLE_NAME', 'rédacteur')

# Authentik OIDC
AUTHENTIK_BASE_URL     = os.getenv('AUTHENTIK_BASE_URL', 'https://auth.drtablebasse.fr')
AUTHENTIK_APP_SLUG     = os.getenv('AUTHENTIK_APP_SLUG', 'hermes')
AUTHENTIK_CLIENT_ID    = os.getenv('AUTHENTIK_CLIENT_ID', '')
AUTHENTIK_CLIENT_SECRET = os.getenv('AUTHENTIK_CLIENT_SECRET', '')
AUTHENTIK_REDIRECT_URI  = os.getenv('AUTHENTIK_REDIRECT_URI', 'http://localhost:8000/auth/callback')

AUTHENTIK_AUTH_URL     = f"{AUTHENTIK_BASE_URL}/application/o/authorize/"
AUTHENTIK_TOKEN_URL    = f"{AUTHENTIK_BASE_URL}/application/o/token/"
AUTHENTIK_USERINFO_URL = f"{AUTHENTIK_BASE_URL}/application/o/userinfo/"
AUTHENTIK_LOGOUT_URL   = f"{AUTHENTIK_BASE_URL}/application/o/{AUTHENTIK_APP_SLUG}/end-session/"

JWT_SECRET      = os.getenv('JWT_SECRET', 'change-me')
JWT_ALGORITHM   = "HS256"
JWT_EXPIRE_DAYS = 7

# Cache guild role name map {role_id: role_name}
_guild_roles: dict[str, str] = {}


# ── JWT ────────────────────────────────────────────────────────────────────────

def create_jwt(user_id: int, username: str, avatar: str | None,
               is_admin: bool, is_redacteur: bool) -> str:
    exp = datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRE_DAYS)
    return jwt.encode({
        "sub":          str(user_id),
        "username":     username,
        "avatar":       avatar,
        "is_admin":     is_admin,
        "is_redacteur": is_redacteur,
        "exp":          exp,
    }, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_jwt(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        return None


# ── Authentik OAuth2 ───────────────────────────────────────────────────────────

def get_oauth_login_url() -> str:
    from urllib.parse import urlencode
    params = {
        "client_id":     AUTHENTIK_CLIENT_ID,
        "response_type": "code",
        "redirect_uri":  AUTHENTIK_REDIRECT_URI,
        "scope":         "openid profile email discord",
    }
    return f"{AUTHENTIK_AUTH_URL}?{urlencode(params)}"


async def exchange_code(code: str) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.post(AUTHENTIK_TOKEN_URL, data={
            "grant_type":   "authorization_code",
            "code":         code,
            "redirect_uri": AUTHENTIK_REDIRECT_URI,
            "client_id":    AUTHENTIK_CLIENT_ID,
            "client_secret": AUTHENTIK_CLIENT_SECRET,
        })
        if not r.is_success:
            raise httpx.HTTPStatusError(
                f"Authentik token error {r.status_code}: {r.text}",
                request=r.request,
                response=r,
            )
        return r.json()


async def get_authentik_userinfo(access_token: str) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.get(AUTHENTIK_USERINFO_URL,
                             headers={"Authorization": f"Bearer {access_token}"})
        r.raise_for_status()
        return r.json()


# ── Discord (via bot token) ────────────────────────────────────────────────────

async def _load_guild_roles():
    global _guild_roles
    if _guild_roles or not DISCORD_TOKEN or not GUILD_ID:
        return
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{DISCORD_API}/guilds/{GUILD_ID}/roles",
                headers={"Authorization": f"Bot {DISCORD_TOKEN}"},
            )
            if r.status_code == 200:
                _guild_roles = {role['id']: role['name'] for role in r.json()}
    except Exception:
        pass


async def get_discord_user(user_id: int) -> Optional[dict]:
    """Fetch Discord user info using bot token."""
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{DISCORD_API}/users/{user_id}",
                headers={"Authorization": f"Bot {DISCORD_TOKEN}"},
            )
            if r.status_code == 200:
                return r.json()
    except Exception:
        pass
    return None


async def get_guild_member(user_id: int) -> Optional[dict]:
    """Fetch guild member using bot token (no user OAuth scope needed)."""
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{DISCORD_API}/guilds/{GUILD_ID}/members/{user_id}",
                headers={"Authorization": f"Bot {DISCORD_TOKEN}"},
            )
            if r.status_code in (200, 201):
                return r.json()
    except Exception:
        pass
    return None


async def resolve_roles(user_id: int) -> tuple[bool, bool]:
    """Return (is_admin, is_redacteur) by checking guild membership via bot token."""
    await _load_guild_roles()
    member = await get_guild_member(user_id)
    if not member:
        return False, False
    role_ids   = set(member.get('roles', []))
    role_names = {_guild_roles.get(rid, '') for rid in role_ids}
    is_admin      = ADMIN_ROLE_NAME in role_names
    is_redacteur  = REDACTEUR_ROLE_NAME in role_names or is_admin
    return is_admin, is_redacteur
