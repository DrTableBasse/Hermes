from typing import Optional
from fastapi import Cookie, HTTPException, Request
from auth import decode_jwt


def get_current_user(token: Optional[str] = Cookie(None, alias="hermes_token")) -> dict:
    if not token:
        raise HTTPException(status_code=401, detail="Non authentifié")
    payload = decode_jwt(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token invalide ou expiré")
    return payload


def require_admin(user: dict = None) -> dict:
    if not user or not user.get('is_admin'):
        raise HTTPException(status_code=403, detail="Rôle Administration requis")
    return user


def require_redacteur(user: dict = None) -> dict:
    if not user or not (user.get('is_redacteur') or user.get('is_admin')):
        raise HTTPException(status_code=403, detail="Rôle rédacteur requis")
    return user
