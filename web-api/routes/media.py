import os
import uuid
from pathlib import Path

import aiofiles
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from middleware.auth_middleware import get_current_user, require_redacteur
import database as db

router    = APIRouter(prefix="/media", tags=["media"])
MEDIA_DIR = Path(os.getenv('MEDIA_DIR', '/app/media'))
ALLOWED_EXTENSIONS  = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.mp4', '.pdf'}
ALLOWED_MIME_PREFIXES = ('image/jpeg', 'image/png', 'image/gif', 'image/webp', 'video/mp4', 'application/pdf')
MAX_SIZE  = 10 * 1024 * 1024  # 10 MB


def _detect_mime(data: bytes) -> str:
    if data[:3] == b'\xff\xd8\xff':
        return 'image/jpeg'
    if data[:8] == b'\x89PNG\r\n\x1a\n':
        return 'image/png'
    if data[:6] in (b'GIF87a', b'GIF89a'):
        return 'image/gif'
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        return 'image/webp'
    if data[:4] in (b'\x00\x00\x00\x18', b'\x00\x00\x00\x1c', b'ftyp'):
        return 'video/mp4'
    if data[:4] == b'%PDF':
        return 'application/pdf'
    return 'application/octet-stream'


@router.post("/upload")
async def upload(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    require_redacteur(user)

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Format non supporté: {ext}")

    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=413, detail="Fichier trop volumineux (max 10 Mo)")

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
    """, int(user['sub']), filename, file.filename, url, len(content))

    return {"url": url, "filename": filename}


@router.get("/{filename}")
async def serve_media(filename: str):
    path = MEDIA_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Fichier introuvable")
    return FileResponse(path)
