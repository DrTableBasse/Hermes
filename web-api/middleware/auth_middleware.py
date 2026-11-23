from typing import Optional
from fastapi import Cookie, HTTPException
import database as db
from permissions import PERMISSIONS

_SESSION_QUERY = """
    SELECT u."discordId", u."isAdmin", u."isRedacteur", u."sitePermissions"
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
        # Clés hors catalogue ignorées : un droit retiré du catalogue ne survit pas en base.
        "permissions":  frozenset(p for p in (row["sitePermissions"] or []) if p in PERMISSIONS),
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


def has_permission(user: Optional[dict], perm: str) -> bool:
    """Vrai si ``user`` est admin (propriétaire ou ``admin_role``) ou détient ``perm``.

    ``perm`` hors catalogue lève ``ValueError`` : une faute de frappe échoue dès le premier appel.
    """
    if perm not in PERMISSIONS:
        raise ValueError(f"Droit inconnu : {perm}")
    if not user:
        return False
    return bool(user.get("is_admin")) or perm in user.get("permissions", frozenset())


def require_permission(user: Optional[dict], perm: str) -> dict:
    if not has_permission(user, perm):
        raise HTTPException(status_code=403, detail=f"Droit requis : {PERMISSIONS[perm]}")
    return user


def require_any_permission(user: Optional[dict], *perms: str) -> dict:
    """403 sauf si ``user`` détient au moins un des ``perms`` (admin : toujours)."""
    if not perms:
        raise ValueError("Au moins un droit attendu")
    if not any([has_permission(user, p) for p in perms]):  # liste : chaque clé est vérifiée
        labels = " ou ".join(PERMISSIONS[p] for p in perms)
        raise HTTPException(status_code=403, detail=f"Droit requis : {labels}")
    return user


def effective_permissions(user: dict) -> list[str]:
    """Droits effectifs triés : tout le catalogue pour un admin."""
    if user.get("is_admin"):
        return sorted(PERMISSIONS)
    return sorted(user.get("permissions", frozenset()))


# Alias de migration (non utilisés dans routes/).
def require_admin(user: dict) -> dict:
    return require_permission(user, "admin.view")


def require_redacteur(user: dict) -> dict:
    return require_permission(user, "articles.write")
