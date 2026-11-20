"""Events programmés Discord (public) : récompense XP lue dans la description, grade de l'organisateur."""
import re
from typing import Optional

from fastapi import APIRouter, Request

import database as db
from bot_client import bot_get, cached
from grades import get_grades, public_grade
from limiter import limiter

router = APIRouter(tags=["events"])

EVENTS_TTL = 60
_XP_RE = re.compile(r"\bxp\s*:\s*(\d{1,6})\b", re.IGNORECASE)


def parse_xp_reward(description: Optional[str]) -> Optional[int]:
    """Récompense XP annoncée dans la description (``XP: 200``), ``None`` sinon."""
    if not description:
        return None
    match = _XP_RE.search(description)
    return int(match.group(1)) if match else None


async def _organizers(creator_ids: list[int]) -> dict[int, dict]:
    if not creator_ids:
        return {}
    rows = await db.fetch(
        """SELECT v.user_id, v.username, v.discord_avatar, x.current_level
           FROM user_voice_data v LEFT JOIN user_xp x ON x.user_id = v.user_id
           WHERE v.user_id = ANY($1::bigint[])""",
        creator_ids,
    )
    grades = await get_grades()
    return {
        int(r["user_id"]): {
            "id": str(r["user_id"]), "name": r["username"], "avatar": r["discord_avatar"],
            "grade": public_grade(int(r["current_level"] or 0), grades),
        }
        for r in rows
    }


async def _build_events():
    data = await bot_get("/events")
    if data is None:
        return None
    raw = sorted(data.get("events", []), key=lambda e: e["start"])
    creator_ids = sorted({int(e["creator_id"]) for e in raw if e.get("creator_id")})
    organizers = await _organizers(creator_ids)
    return {"events": [
        {**e, "id": str(e["id"]),
         "creator_id": None if e.get("creator_id") is None else str(e["creator_id"]),
         "xp_reward": parse_xp_reward(e.get("description")),
         "organizer": organizers.get(int(e["creator_id"])) if e.get("creator_id") else None}
        for e in raw
    ]}


@router.get("/events")
@limiter.limit("60/minute")
async def get_events(request: Request):
    payload = await cached("events", EVENTS_TTL, _build_events)
    if payload is None:
        return {"events": [], "stale": True}
    return payload
