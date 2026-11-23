import os
import uuid
from pathlib import Path

import aiofiles
from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.datastructures import UploadFile
from middleware.auth_middleware import get_current_user, require_redacteur
import database as db

router    = APIRouter(prefix="/media", tags=["media"])
MEDIA_DIR = Path(os.getenv('MEDIA_DIR', '/app/media'))
ALLOWED_EXTENSIONS  = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.mp4', '.pdf'}
ALLOWED_MIME_PREFIXES = ('image/jpeg', 'image/png', 'image/gif', 'image/webp', 'video/mp4', 'application/pdf')
MAX_SIZE  = 10 * 1024 * 1024  # 10 MB
# Corps multipart complet : le fichier plus les en-têtes de parties (constat M6).
MAX_BODY  = MAX_SIZE + 64 * 1024
CHUNK     = 64 * 1024


def _too_large() -> HTTPException:
    return HTTPException(status_code=413, detail="Fichier trop volumineux (max 10 Mo)")


def _capped_receive(receive, limit: int):
    """`receive` ASGI qui refuse (413) dès que le corps reçu dépasse `limit` octets."""
    seen = 0

    async def wrapped():
        nonlocal seen
        message = await receive()
        if message["type"] == "http.request":
            seen += len(message.get("body", b""))
            if seen > limit:
                raise _too_large()
        return message
    return wrapped


def _detect_mime(data: bytes) -> str:
    if data[:3] == b'\xff\xd8\xff':
        return 'image/jpeg'
    if data[:8] == b'\x89PNG\r\n\x1a\n':
        return 'image/png'
    if data[:6] in (b'GIF87a', b'GIF89a'):
        return 'image/gif'
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        return 'image/webp'
    # Boîte ISO BMFF « ftyp » en tête : 4 octets de taille, puis « ftyp » (constat M6).
    if data[4:8] == b'ftyp':
        return 'video/mp4'
    if data[:4] == b'%PDF':
        return 'application/pdf'
    return 'application/octet-stream'


@router.post("/upload")
async def upload(request: Request, user: dict = Depends(get_current_user)):
    require_redacteur(user)

    # Taille contrôlée avant toute lecture (Content-Length), puis en flux : le corps n'est jamais
    # lu au-delà de la limite, même sans Content-Length (envoi « chunked »).
    try:
        declared = int(request.headers.get("content-length", "0"))
    except ValueError:
        raise HTTPException(status_code=400, detail="Content-Length invalide")
    if declared > MAX_BODY:
        raise _too_large()
    capped = Request(request.scope, _capped_receive(request.receive, MAX_BODY))
    form = await capped.form(max_files=1, max_fields=5)
    try:
        file = form.get("file")
        if not isinstance(file, UploadFile) or not file.filename:
            raise HTTPException(status_code=422, detail="Fichier manquant")

        ext = Path(file.filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"Format non supporté: {ext}")

        chunks, size = [], 0
        while chunk := await file.read(CHUNK):
            size += len(chunk)
            if size > MAX_SIZE:
                raise _too_large()
            chunks.append(chunk)
        content = b"".join(chunks)
        original_name = file.filename
    finally:
        await form.close()

    # Validate magic bytes — extension alone is not sufficient
    detected_mime = _detect_mime(content)
    if not any(detected_mime.startswith(p) for p in ALLOWED_MIME_PREFIXES):
        raise HTTPException(status_code=400, detail=f"Type de fichier non autorisé: {detected_mime}")

    filename = f"{uuid.uuid4()}{ext}"
    dest     = MEDIA_DIR / filename
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)

    async with aiofiles.open(dest, 'wb') as f:
        await f.write(content)

    url = f"/media/{filename}"
    await db.execute("""
        INSERT INTO media (uploaded_by, filename, original_name, url, size)
        VALUES ($1, $2, $3, $4, $5)
    """, int(user['sub']), filename, original_name, url, len(content))

    return {"url": url, "filename": filename}


# Lecture : servie par le montage `MediaFiles` de main.py (PDF en pièce jointe, dossier → 404,
# galerie masquée réservée aux admins). L'ancienne route GET /media/{filename} est supprimée.
