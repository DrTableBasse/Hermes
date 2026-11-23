"""Service statique de `/media` (volume `media_data`), avec les règles de sécurité des médias.

- Constat M6 : un PDF est servi en `Content-Disposition: attachment` (jamais affiché sur
  l'origine du site) ; un dossier répond 404 (comportement de `StaticFiles` sans `html=True`).
- Constat M7 : un élément de galerie masqué par un admin n'est plus servi publiquement. Le
  fichier reste en place (démasquage immédiat, sans déplacement) ; seule une session admin le
  voit encore, pour la modération (`/admin/galerie` l'affiche par `<img>`, cookie relayé par le
  rewrite `/media/*` de Next).
"""
from pathlib import PurePosixPath

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


async def _gallery_item_hidden(file_name: str) -> bool:
    return bool(await db.fetchval(
        "SELECT hidden FROM gallery_items WHERE file_name = $1", file_name))


class MediaFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        parts = PurePosixPath(path.replace("\\", "/")).parts
        if len(parts) == 2 and parts[0] == "gallery":
            if await _gallery_item_hidden(parts[1]) and not await _is_admin(scope):
                raise HTTPException(status_code=404)
        response = await super().get_response(path, scope)
        if PurePosixPath(path).suffix.lower() in ATTACHMENT_EXTENSIONS and response.status_code == 200:
            response.headers["content-disposition"] = "attachment"
        return response
