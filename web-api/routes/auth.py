from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Cookie, HTTPException, Response
from fastapi.responses import RedirectResponse

import database as db
from auth import (
    create_jwt, decode_jwt,
    exchange_code, get_authentik_userinfo,
    get_discord_user, resolve_roles,
    get_oauth_login_url, AUTHENTIK_LOGOUT_URL,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/login")
async def login():
    return RedirectResponse(get_oauth_login_url())


@router.get("/callback")
async def callback(code: str, response: Response):
    try:
        tokens   = await exchange_code(code)
        userinfo = await get_authentik_userinfo(tokens['access_token'])
    except Exception as e:
        detail = str(e)
        raise HTTPException(status_code=400, detail=f"Erreur OAuth2 Authentik : {detail}")

    # The discord_id claim comes from the Scope Mapping created in Authentik
    discord_id_raw = userinfo.get('discord_id')
    if not discord_id_raw:
        raise HTTPException(
            status_code=400,
            detail=f"Impossible de récupérer l'ID Discord. Userinfo reçu : {userinfo}"
        )

    user_id  = int(discord_id_raw)
    username = userinfo.get('preferred_username') or userinfo.get('name', f"User_{user_id}")

    # Fetch Discord avatar via bot token
    discord_user = await get_discord_user(user_id)
    avatar = None
    if discord_user and discord_user.get('avatar'):
        avatar = f"https://cdn.discordapp.com/avatars/{user_id}/{discord_user['avatar']}.png"

    # Check guild roles via bot token
    is_admin, is_redacteur = await resolve_roles(user_id)

    # Upsert user in DB
    await db.execute("""
        INSERT INTO user_voice_data (user_id, username, discord_avatar, last_seen)
        VALUES ($1, $2, $3, NOW())
        ON CONFLICT (user_id) DO UPDATE
          SET username       = EXCLUDED.username,
              discord_avatar = COALESCE(EXCLUDED.discord_avatar, user_voice_data.discord_avatar),
              last_seen      = NOW(),
              updated_at     = NOW()
    """, user_id, username, avatar)

    # Store Authentik session token (for potential future refresh)
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    await db.execute("""
        INSERT INTO user_sessions (user_id, access_token, refresh_token, expires_at)
        VALUES ($1, $2, $3, $4)
    """, user_id, tokens['access_token'], tokens.get('refresh_token'), expires_at)

    jwt_token = create_jwt(user_id, username, avatar, is_admin, is_redacteur)
    resp      = RedirectResponse(url="/")
    resp.set_cookie(
        key="hermes_token", value=jwt_token,
        httponly=True, secure=False, samesite="lax",
        max_age=7 * 24 * 3600,
    )
    return resp


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("hermes_token")
    return {"success": True, "redirect": AUTHENTIK_LOGOUT_URL}


@router.get("/me")
async def me(token: str | None = Cookie(None, alias="hermes_token")):
    if not token:
        raise HTTPException(status_code=401, detail="Non authentifié")
    payload = decode_jwt(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token invalide ou expiré")
    return {
        "user_id":      payload["sub"],
        "username":     payload["username"],
        "avatar":       payload["avatar"],
        "is_admin":     payload["is_admin"],
        "is_redacteur": payload["is_redacteur"],
    }
