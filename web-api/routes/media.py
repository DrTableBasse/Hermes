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
ALLOWED   = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
MAX_SIZE  = 10 * 1024 * 1024  # 10 MB


@router.post("/upload")
async def upload(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    require_redacteur(user)

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED:
        raise HTTPException(status_code=400, detail=f"Format non supporté: {ext}")

    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=413, detail="Fichier trop volumineux (max 10 Mo)")

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
