"""La caserne en direct : état du serveur Discord pour la page d'accueil (public)."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Request, Response

import database as db
from bot_client import bot_get, cached
from limiter import limiter

router = APIRouter(tags=["live"])

PARIS = ZoneInfo("Europe/Paris")
LIVE_TTL = 30
FEED_TTL = 60
FEED_SIZE = 10


def _hour_floor(moment: datetime) -> datetime:
    return moment.replace(minute=0, second=0, microsecond=0)


async def _curve_24h(now: datetime) -> list[dict]:
    """24 points (moyenne horaire des connectés) ; une heure sans relevé vaut 0."""
    last = _hour_floor(now)
    hours = [last - timedelta(hours=h) for h in range(23, -1, -1)]
    rows = await db.fetch(
        """SELECT date_trunc('hour', taken_at) AS hour, AVG(online) AS online
           FROM guild_stats_snapshots WHERE taken_at >= $1 GROUP BY 1""",
        hours[0],
    )
    by_hour = {r["hour"].astimezone(timezone.utc): r["online"] for r in rows}
    return [{"hour": h.isoformat(), "online": round(by_hour.get(h) or 0)} for h in hours]


async def _build_live():
    latest = await db.fetchrow(
        "SELECT taken_at, members, online, in_voice FROM guild_stats_snapshots "
        "ORDER BY taken_at DESC LIMIT 1"
    )
    if not latest:
        return None
    now = datetime.now(timezone.utc)
    live = await bot_get("/live")
    if live:
        state = {
            "members": live["members"], "online": live["online"], "in_voice": live["in_voice"],
            "voice_avatars": live.get("voice_avatars", []), "game_players": live.get("game_players", {}),
            "stale": False, "updated_at": now.isoformat(),
        }
    else:
        state = {
            "members": latest["members"], "online": latest["online"], "in_voice": latest["in_voice"],
            "voice_avatars": [], "game_players": {},
            "stale": True, "updated_at": latest["taken_at"].isoformat(),
        }
    midnight = datetime.now(PARIS).replace(hour=0, minute=0, second=0, microsecond=0)
    messages = await db.fetchval(
        "SELECT COALESCE(SUM(messages), 0) FROM guild_stats_snapshots WHERE taken_at >= $1", midnight
    )
    return {**state, "messages_today": int(messages or 0), "curve_24h": await _curve_24h(now)}


@router.get("/live")
@limiter.limit("60/minute")
async def get_live(request: Request):
    payload = await cached("live", LIVE_TTL, _build_live)
    if payload is None:
        return Response(status_code=204)
    return payload


async def _build_feed():
    rows = await db.fetch(
        """SELECT type, user_id, username, avatar, label, at FROM (
               SELECT 'level_up' AS type, n.user_id, u.username, u.discord_avatar AS avatar,
                      n.title AS label, n.created_at AS at
               FROM user_notifications n JOIN user_voice_data u ON u.user_id = n.user_id
               WHERE n.type = 'level_up' AND u.is_member
               UNION ALL
               SELECT 'achievement', ua.user_id, u.username, u.discord_avatar,
                      TRIM(COALESCE(a.icon, '') || ' ' || a.name), ua.unlocked_at
               FROM user_achievements ua
               JOIN achievements a ON a.id = ua.achievement_id
               JOIN user_voice_data u ON u.user_id = ua.user_id
               WHERE u.is_member
           ) feed ORDER BY at DESC LIMIT $1""",
        FEED_SIZE,
    )
    return {"items": [
        {"type": r["type"], "user_id": str(r["user_id"]), "username": r["username"],
         "avatar": r["avatar"], "label": r["label"], "at": r["at"].isoformat()}
        for r in rows
    ]}


@router.get("/live/feed")
@limiter.limit("60/minute")
async def get_live_feed(request: Request):
    return await cached("live-feed", FEED_TTL, _build_feed)
