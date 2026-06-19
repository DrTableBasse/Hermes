from typing import Optional
from fastapi import Cookie, HTTPException
import database as db

_SESSION_QUERY = """
    SELECT u."discordId", u."isAdmin", u."isRedacteur"
    FROM session s
    JOIN "user" u ON u.id = s."userId"
    WHERE s.token = $1 AND s."expiresAt" > NOW()
"""


async def _fetch_session(session_token: str) -> Optional[dict]:
    # BetterAuth appends ".{signature}" to the token in browser cookies — strip it
    token = session_token.split('.')[0]
    row = await db.fetchrow(_SESSION_QUERY, token)
    if not row:
        return None
    return {
        "sub":          row["discordId"],
        "is_admin":     row["isAdmin"],
        "is_redacteur": row["isRedacteur"],
    }


async def get_current_user(
    session_token: Optional[str] = Cookie(None, alias="better-auth.session_token"),
) -> dict:
    if not session_token:
        raise HTTPException(status_code=401, detail="Non authentifié")
    user = await _fetch_session(session_token)
    if not user:
        raise HTTPException(status_code=401, detail="Session invalide ou expirée")
    return user


async def get_optional_user(
    session_token: Optional[str] = Cookie(None, alias="better-auth.session_token"),
) -> Optional[dict]:
    if not session_token:
        return None
    return await _fetch_session(session_token)


def require_admin(user: dict) -> dict:
    if not user or not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Rôle Administration requis")
    return user


def require_redacteur(user: dict) -> dict:
    if not user or not (user.get("is_redacteur") or user.get("is_admin")):
        raise HTTPException(status_code=403, detail="Rôle rédacteur requis")
    return user
