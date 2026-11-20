"""Catalogue public des succès, avec le nombre de membres actifs qui ont débloqué chacun d'eux.

Le site en déduit la rareté réelle (part des membres) ; aucune rareté n'est stockée en base.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Request

import database as db
from bot_client import cached
from limiter import limiter

log = logging.getLogger(__name__)
router = APIRouter(tags=["achievements"])

CATALOG_TTL = 300

# Seuls les membres encore sur le serveur (`is_member`) comptent : même population que `members_total`.
_CATALOG_SQL = """
    SELECT a.id, a.name, a.description, a.icon, a.points, a.condition_type,
           COUNT(v.user_id) AS unlocked_count
    FROM achievements a
    LEFT JOIN user_achievements ua ON ua.achievement_id = a.id
    LEFT JOIN user_voice_data v ON v.user_id = ua.user_id AND v.is_member
    GROUP BY a.id
    ORDER BY a.points DESC, a.id
"""


async def _load() -> Optional[dict]:
    """Catalogue complet ; ``None`` si la base est illisible (``cached`` ne mémorise pas ``None``)."""
    try:
        rows = await db.fetch(_CATALOG_SQL)
        total = await db.fetchval("SELECT COUNT(*) FROM user_voice_data WHERE is_member")
    except Exception as exc:
        log.warning("Lecture du catalogue des succès impossible : %s", exc)
        return None
    return {
        "achievements": [
            {
                "id": r["id"],
                "name": r["name"],
                "description": r["description"],
                "icon": r["icon"],
                "points": int(r["points"] or 0),
                "condition_type": r["condition_type"],
                "unlocked_count": int(r["unlocked_count"] or 0),
            }
            for r in rows
        ],
        "members_total": int(total or 0),
    }


@router.get("/achievements")
@limiter.limit("60/minute")
async def list_achievements(request: Request):
    data = await cached("achievements-catalog", CATALOG_TTL, _load)
    if data is None:
        return {"achievements": [], "members_total": 0, "stale": True}
    return data
