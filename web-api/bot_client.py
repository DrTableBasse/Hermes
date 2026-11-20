"""Client HTTP minimal vers l'API interne du bot.

Toute erreur (réseau, délai, statut >= 400, corps non JSON) renvoie ``None`` :
l'appelant décide quoi faire quand le bot est injoignable.
"""
import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


def _url(path: str) -> str:
    return f"{os.getenv('BOT_API_URL', 'http://bot:8001')}{path}"


def _headers() -> dict:
    return {"Authorization": f"Bearer {os.getenv('BOT_API_TOKEN', '')}"}


async def _request(method: str, path: str, timeout: float, **kwargs) -> Optional[dict]:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.request(method, _url(path), headers=_headers(), **kwargs)
        if r.status_code >= 400:
            logger.warning("bot %s %s -> %s", method, path, r.status_code)
            return None
        return r.json()
    except Exception as e:  # réseau, délai, JSON invalide
        logger.warning("bot %s %s injoignable : %s", method, path, e)
        return None


async def bot_get(path: str, timeout: float = 1.5) -> Optional[dict]:
    return await _request("GET", path, timeout)


async def bot_post(path: str, json: Optional[dict] = None, timeout: float = 1.5) -> Optional[dict]:
    return await _request("POST", path, timeout, json=json)
