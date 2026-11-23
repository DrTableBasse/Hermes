"""Service statique de `/media` (volume `media_data`), avec les règles de sécurité des médias.

- Constat M6 : un PDF est servi en `Content-Disposition: attachment` (jamais affiché sur
  l'origine du site) ; un dossier répond 404 (comportement de `StaticFiles` sans `html=True`).
- Constat M7 : un élément de galerie masqué par un admin n'est plus servi publiquement. Le
  fichier reste en place (démasquage immédiat, sans déplacement) ; seule une session admin le
  voit encore, pour la modération (`/admin/galerie` l'affiche par `<img>`, cookie relayé par le
  rewrite `/media/*` de Next).
- Constat m4 : `/media` est hors limiteur. Une image de galerie absente répond 404 sans toucher
  la base, et les noms masqués sont gardés en mémoire (`HIDDEN_TTL` secondes, invalidés par
  les routes admin de la galerie) : au plus une requête SQL par période, quel que soit le trafic.
"""
import asyncio
import stat
import time
from pathlib import PurePosixPath

import anyio
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.staticfiles import StaticFiles

import database as db
from middleware import auth_middleware

SESSION_COOKIES = ("better-auth.session_token", "__Secure-better-auth.session_token")
ATTACHMENT_EXTENSIONS = {".pdf"}


async def _is_admin(scope) -> bool:
    cookies = Request(scope).cookies
    token = next((cookies[name] for name in SESSION_COOKIES if cookies.get(name)), None)
    if not token:
        return False
    user = await auth_middleware._fetch_session(token)
    return bool(user and user.get("is_admin"))


HIDDEN_TTL = 30.0
_hidden: frozenset[str] = frozenset()
_hidden_expires = 0.0
_hidden_lock = asyncio.Lock()


def invalidate_hidden_gallery() -> None:
    """À appeler après tout changement de visibilité (PATCH/DELETE admin de la galerie)."""
    global _hidden_expires
    _hidden_expires = 0.0


async def _hidden_gallery_names() -> frozenset[str]:
    global _hidden, _hidden_expires
    if time.monotonic() < _hidden_expires:
        return _hidden
    async with _hidden_lock:
        # Une seule requête pour les requêtes concurrentes arrivées pendant le rechargement.
        if time.monotonic() >= _hidden_expires:
            rows = await db.fetch("SELECT file_name FROM gallery_items WHERE hidden = TRUE")
            _hidden = frozenset(r["file_name"] for r in rows if r["file_name"])
            _hidden_expires = time.monotonic() + HIDDEN_TTL
    return _hidden


async def _gallery_item_hidden(file_name: str) -> bool:
    return file_name in await _hidden_gallery_names()


class MediaFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        parts = PurePosixPath(path.replace("\\", "/")).parts
        if len(parts) == 2 and parts[0] == "gallery":
            # Fichier absent ou dossier : le 404 de StaticFiles suffit, sans requête SQL.
            _, found = await anyio.to_thread.run_sync(self.lookup_path, path)
            if found is None or not stat.S_ISREG(found.st_mode):
                raise HTTPException(status_code=404)
            if await _gallery_item_hidden(parts[1]) and not await _is_admin(scope):
                raise HTTPException(status_code=404)
        response = await super().get_response(path, scope)
        if PurePosixPath(path).suffix.lower() in ATTACHMENT_EXTENSIONS and response.status_code == 200:
            response.headers["content-disposition"] = "attachment"
        return response
