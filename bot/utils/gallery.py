"""Galerie : contrôles purs (aucune connexion Discord ni base).

Les signatures d'image reprennent celles de ``web-api/routes/media.py``.
"""
import re
from typing import Optional
from urllib.parse import urlparse

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


def classify_clip(url: str) -> Optional[str]:
    """``youtube|twitch|medal`` selon l'hôte exact (pas de simple sous-chaîne), sinon ``None``."""
    try:
        parsed = urlparse(url.strip())
        host = (parsed.hostname or "").lower()
    except ValueError:
        return None
    if parsed.scheme not in ("http", "https"):
        return None
    path = parsed.path or ""
    if host in ("youtube.com", "www.youtube.com", "m.youtube.com"):
        return "youtube" if path.startswith("/watch") else None
    if host == "youtu.be":
        return "youtube" if len(path) > 1 else None
    if host == "clips.twitch.tv":
        return "twitch" if len(path) > 1 else None
    if host in ("twitch.tv", "www.twitch.tv", "m.twitch.tv"):
        return "twitch" if "/clip/" in path else None
    if host in ("medal.tv", "www.medal.tv"):
        return "medal" if len(path) > 1 else None
    return None


def find_clip_url(text: Optional[str]) -> Optional[str]:
    """Premier lien de clip reconnu dans le texte du message."""
    for match in _URL_RE.finditer(text or ""):
        url = match.group(0).rstrip(".,;:!?)>")
        if classify_clip(url):
            return url
    return None
