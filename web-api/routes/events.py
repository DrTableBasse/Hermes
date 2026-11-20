"""Events programmés Discord (public) : récompense XP lue dans la description, grade de l'organisateur."""
import logging
import re
from typing import Optional

from fastapi import APIRouter, Request

import database as db
from bot_client import bot_get, cached
from grades import get_grades, public_grade
from limiter import limiter

log = logging.getLogger(__name__)
router = APIRouter(tags=["events"])

EVENTS_TTL = 60
_XP_RE = re.compile(r"\bxp\s*:\s*(\d{1,6})\b", re.IGNORECASE)
_last_good: Optional[dict] = None  # dernière réponse valide, resservie (stale) quand le bot est muet


def parse_xp_reward(description: Optional[str]) -> Optional[int]:
    """Récompense XP annoncée dans la description (``XP: 200``), ``None`` sinon."""
    if not description:
        return None
    match = _XP_RE.search(description)
    return int(match.group(1)) if match else None


async def _organizers(creator_ids: list[int]) -> dict[int, dict]:
    """Organisateurs par id ; base indisponible → ``{}`` (organisateur ``null`` partout)."""
    if not creator_ids:
        return {}
    try:
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
    except Exception as exc:
        log.warning("Organisateurs d'events indisponibles : %s", exc)
        return {}


def _valid(event) -> bool:
    """Un event exploitable : dict avec ``id``, ``start`` et ``creator_id`` absent ou numérique."""
    try:
        if not (isinstance(event, dict) and event["id"] is not None and event["start"]):
            return False
        if event.get("creator_id") is not None:
            int(event["creator_id"])
        return True
    except (KeyError, TypeError, ValueError):
        return False


async def _build_events():
    data = await bot_get("/events")
    if data is None:
        return None
    try:
        items = data["events"]
        raw = [e for e in items if _valid(e)]
        if len(raw) < len(items):
            log.warning("%d event(s) mal formé(s) ignoré(s)", len(items) - len(raw))
        raw.sort(key=lambda e: e["start"])
        creator_ids = sorted({int(e["creator_id"]) for e in raw if e.get("creator_id")})
        organizers = await _organizers(creator_ids)
        return {"events": [
            {**e, "id": str(e["id"]),
             "creator_id": None if e.get("creator_id") is None else str(e["creator_id"]),
             "xp_reward": parse_xp_reward(e.get("description")),
             "organizer": organizers.get(int(e["creator_id"])) if e.get("creator_id") else None}
            for e in raw
        ]}
    except Exception:
        log.exception("Construction des events impossible : repli sur le dernier état connu")
        return None


@router.get("/events")
@limiter.limit("60/minute")
async def get_events(request: Request):
    global _last_good
    payload = await cached("events", EVENTS_TTL, _build_events)
    if payload is None:
        if _last_good is not None:
            return {**_last_good, "stale": True}
        return {"events": [], "stale": True}
    _last_good = payload
    return payload
