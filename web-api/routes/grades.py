import re
import unicodedata

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Path, Request

import database as db
from grades import clear_grades_cache, get_grades
from limiter import limiter
from middleware.auth_middleware import get_current_user, require_permission

router = APIRouter(tags=["grades"])


@router.get("/grades")
@limiter.limit("60/minute")
async def list_grades(request: Request):
    return {"grades": await get_grades()}


# ── Écriture (admin) ──────────────────────────────────────────────────────────

NAME_MAX = 40
LEVEL_MAX = 1000
_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


@router.put("/admin/grades/{slug}")
async def update_grade(body: dict, slug: str = Path(pattern=r"^[a-z0-9-]{1,32}$"),
                       user: dict = Depends(get_current_user)):
    require_permission(user, "content.edit")
    name, color, level_min = body.get("name"), body.get("color"), body.get("level_min")
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > NAME_MAX             or any(unicodedata.category(c) in ("Cc", "Zl", "Zp") for c in name):
        raise HTTPException(422, f"Nom requis ({NAME_MAX} caractères maximum, sur une ligne)")
    if not isinstance(color, str) or not _COLOR_RE.fullmatch(color):
        raise HTTPException(422, "Couleur invalide (format #RRGGBB)")
    if isinstance(level_min, bool) or not isinstance(level_min, int) or not 1 <= level_min <= LEVEL_MAX:
        raise HTTPException(422, f"Niveau minimum invalide (1 à {LEVEL_MAX})")
    if slug == "recrue" and level_min != 1:
        raise HTTPException(422, "Le grade « recrue » commence au niveau 1")
    if await db.fetchval("SELECT 1 FROM grades WHERE level_min = $1 AND slug <> $2", level_min, slug):
        raise HTTPException(409, "Un autre grade commence déjà à ce niveau")
    try:
        updated = await db.fetchval(
            "UPDATE grades SET name = $2, color = $3, level_min = $4 WHERE slug = $1 RETURNING 1",
            slug, name.strip(), color.upper(), level_min)
    except asyncpg.UniqueViolationError:  # course avec une autre écriture
        raise HTTPException(409, "Un autre grade commence déjà à ce niveau")
    if not updated:
        raise HTTPException(404, "Grade inconnu")
    clear_grades_cache()
    return {"ok": True}
