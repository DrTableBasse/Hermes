"""
Auth routes — OAuth2 and session management is handled by BetterAuth (Next.js web service).
This router is kept as a placeholder; all /auth/* endpoints are now served by Next.js at /api/auth/*.
"""
from fastapi import APIRouter, Cookie, HTTPException
from middleware.auth_middleware import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me")
async def me(session_token: str | None = Cookie(None, alias="better-auth.session_token")):
    """Return the current user from the active BetterAuth session."""
    from middleware.auth_middleware import get_optional_user
    user = await get_optional_user(session_token)
    if not user:
        raise HTTPException(status_code=401, detail="Non authentifié")
    return {
        "user_id":      user["sub"],
        "is_admin":     user["is_admin"],
        "is_redacteur": user["is_redacteur"],
    }
