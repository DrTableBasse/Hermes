"""Galerie : contrôles purs (aucune connexion Discord ni base).

Les signatures d'image reprennent celles de ``web-api/routes/media.py``.
"""
import asyncio
import logging
import re
from pathlib import PurePath
from typing import Optional
from urllib.parse import parse_qs, urlparse

logger = logging.getLogger(__name__)

MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 Mo, comme l'upload du site

_URL_RE = re.compile(r"https?://[^\s<>]+", re.IGNORECASE)


def sniff_image(data: bytes) -> Optional[str]:
    """Extension (``jpg|png|webp|gif``) d'après les octets magiques, ``None`` sinon."""
    if data[:3] == b"\xff\xd8\xff":
        return "jpg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def accept_attachment(size: int, data: bytes) -> bool:
    """Taille déclarée dans la limite et contenu qui est bien une image."""
    return size <= MAX_IMAGE_BYTES and sniff_image(data) is not None


_YT_ID = re.compile(r"[A-Za-z0-9_-]{11}")
_SLUG = re.compile(r"[A-Za-z0-9_-]+")
_UNSAFE = re.compile(r"[\\@\"'\s\x00-\x1f\x7f]")


def canonical_clip(url: str) -> Optional[tuple[str, str]]:
    """``(fournisseur, URL canonique)`` reconstruite, ``None`` si l'URL n'est pas un clip sûr.

    Jamais le texte brut : une barre oblique inverse ou un ``@`` trompe ``urlparse`` (les
    navigateurs lisent l'hôte autrement), donc toute URL qui en contient est refusée.
    """
    url = url.strip()
    if _UNSAFE.search(url):
        return None
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
    except ValueError:
        return None
    if parsed.scheme not in ("http", "https") or parsed.netloc.lower() != host:
        return None  # identifiants (user@) ou port : refusés
    segments = [seg for seg in parsed.path.split("/") if seg]
    if host in ("youtube.com", "www.youtube.com", "m.youtube.com") and parsed.path == "/watch":
        ids = parse_qs(parsed.query).get("v", [])
        if len(ids) == 1 and _YT_ID.fullmatch(ids[0]):
            return "youtube", f"https://www.youtube.com/watch?v={ids[0]}"
    elif host == "youtu.be" and len(segments) == 1 and _YT_ID.fullmatch(segments[0]):
        return "youtube", f"https://www.youtube.com/watch?v={segments[0]}"
    elif host == "clips.twitch.tv" and len(segments) == 1 and _SLUG.fullmatch(segments[0]):
        return "twitch", f"https://clips.twitch.tv/{segments[0]}"
    elif (host in ("twitch.tv", "www.twitch.tv", "m.twitch.tv") and len(segments) == 3
          and segments[1] == "clip" and _SLUG.fullmatch(segments[0])
          and _SLUG.fullmatch(segments[2])):
        return "twitch", f"https://clips.twitch.tv/{segments[2]}"
    elif (host in ("medal.tv", "www.medal.tv") and segments
          and all(_SLUG.fullmatch(seg) for seg in segments)):
        return "medal", "https://medal.tv/" + "/".join(segments)
    return None


def classify_clip(url: str) -> Optional[str]:
    """``youtube|twitch|medal`` si l'URL est un clip sûr, sinon ``None``."""
    clip = canonical_clip(url)
    return clip[0] if clip else None


def find_clip_url(text: Optional[str]) -> Optional[str]:
    """URL canonique du premier lien de clip sûr du message."""
    for match in _URL_RE.finditer(text or ""):
        clip = canonical_clip(match.group(0).rstrip(".,;:!?)>"))
        if clip:
            return clip[1]
    return None


async def forget_message(db, gallery_dir, message_id: int) -> Optional[str]:
    """Message supprimé sur Discord : sa ligne disparaît de la galerie, et son fichier du volume.

    Le simple masquage laissait ``/media/gallery/<uuid>`` en accès public. Le masquage par
    un admin (réversible, depuis le site) garde, lui, le fichier. ``db`` : objet exposant
    ``fetchval`` (``db_manager``). Renvoie le nom du fichier effacé, ou ``None``.
    """
    file_name = await db.fetchval(
        "DELETE FROM gallery_items WHERE message_id = $1 RETURNING file_name", message_id
    )
    if not file_name:
        return None
    # .name : le nom vient de la base, jamais un chemin hors du dossier.
    path = gallery_dir / PurePath(file_name).name
    try:
        await asyncio.to_thread(path.unlink, True)
    except OSError:
        logger.warning("Fichier de galerie non supprimé : %s", path, exc_info=True)
    return file_name
