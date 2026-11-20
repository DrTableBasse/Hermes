"""Galerie : lecture publique, modération admin (masquer / supprimer)."""
import os
from pathlib import Path

from fastapi import APIRouter, Query, Request

import database as db
from limiter import limiter

router = APIRouter(tags=["gallery"])

GALLERY_DIR = Path(os.getenv("MEDIA_DIR", "/app/media")) / "gallery"

_SELECT = """
    SELECT g.id, g.kind, g.file_name, g.clip_url, g.clip_provider, g.caption,
           g.author_id, g.created_at, v.username, v.discord_avatar
    FROM gallery_items g
    LEFT JOIN user_voice_data v ON v.user_id = g.author_id
    WHERE g.hidden = FALSE {extra}
    ORDER BY created_at DESC
    LIMIT $1
"""


def _item(row) -> dict:
    is_image = row["kind"] == "image"
    return {
        "id": row["id"],
        "kind": row["kind"],
        "url": f"/media/gallery/{row['file_name']}" if is_image else row["clip_url"],
        "provider": None if is_image else row["clip_provider"],
        "caption": row["caption"],
        "author": {"id": str(row["author_id"]), "name": row["username"] or "Membre",
                   "avatar": row["discord_avatar"]},
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }


@router.get("/gallery")
@limiter.limit("60/minute")
async def list_gallery(request: Request, limit: int = Query(30, ge=1, le=100)):
    rows = await db.fetch(_SELECT.format(extra=""), limit)
    return {"items": [_item(r) for r in rows]}


@router.get("/gallery/highlights")
@limiter.limit("60/minute")
async def gallery_highlights(request: Request):
    """3 éléments les plus récents des 7 derniers jours ; repli : 3 plus récents."""
    rows = await db.fetch(_SELECT.format(extra="AND g.created_at > NOW() - INTERVAL '7 days'"), 3)
    if not rows:
        rows = await db.fetch(_SELECT.format(extra=""), 3)
    return {"items": [_item(r) for r in rows]}
