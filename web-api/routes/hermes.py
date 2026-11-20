"""Statut d'Hermes (public) : en ligne, latence, disponibilité 30 j, commandes servies, activité du jour."""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Request

import database as db
from bot_client import bot_get, cached
from limiter import limiter

log = logging.getLogger(__name__)
router = APIRouter(tags=["hermes"])

PARIS = ZoneInfo("Europe/Paris")
STATUS_TTL = 30
WINDOW = timedelta(days=30)
WINDOW_MINUTES = 30 * 24 * 60
_last_good: Optional[dict] = None  # dernière réponse complète, resservie si la construction échoue


def availability(heartbeat_minutes: int, since: datetime, now: datetime) -> dict:
    """Disponibilité sur 30 j ; ``percent`` reste ``None`` tant que ``now - since < 30 jours``."""
    if now - since < WINDOW:
        return {"percent": None, "since": since.isoformat()}
    percent = min(100.0, heartbeat_minutes / WINDOW_MINUTES * 100)
    return {"percent": round(percent, 2), "since": since.isoformat()}


class _Degraded(Exception):
    """Au moins une requête a échoué : le payload partiel n'est ni mis en cache ni promu."""

    def __init__(self, payload: dict):
        super().__init__("statut dégradé")
        self.payload = payload


async def _safe(failed: list, label: str, coro_factory, default=None):
    """Une requête de la page ne doit jamais faire tomber la route : ``default`` (None) et trace de l'échec."""
    try:
        return await coro_factory()
    except Exception as exc:
        log.warning("Statut Hermes — %s indisponible : %s", label, exc)
        failed.append(label)
        return default


async def _availability(now: datetime) -> dict:
    row = await db.fetchrow(
        "SELECT (SELECT COUNT(*) FROM bot_heartbeats WHERE minute >= $1) AS n, "
        "(SELECT MIN(minute) FROM bot_heartbeats) AS first",
        now - WINDOW,
    )
    if not row or row["first"] is None:
        return {"percent": None, "since": None}
    return availability(int(row["n"] or 0), row["first"], now)


async def _count(sql: str, *args) -> int:
    return int(await db.fetchval(sql, *args) or 0)


async def _curve(now: datetime) -> list[dict]:
    """24 points : messages par heure (somme des relevés) ; heure sans relevé → ``None``."""
    last = now.replace(minute=0, second=0, microsecond=0)
    hours = [last - timedelta(hours=h) for h in range(23, -1, -1)]
    rows = await db.fetch(
        """SELECT date_trunc('hour', taken_at) AS hour, SUM(messages) AS messages
           FROM guild_stats_snapshots WHERE taken_at >= $1 GROUP BY 1""",
        hours[0],
    )
    by_hour = {r["hour"].astimezone(timezone.utc): r["messages"] for r in rows}
    return [{"hour": h.isoformat(), "messages": None if by_hour.get(h) is None else int(by_hour[h])}
            for h in hours]


def _latency(bot: Optional[dict]) -> Optional[int]:
    try:
        return int(bot["latency_ms"])
    except (KeyError, TypeError, ValueError):
        return None


async def _build_status() -> dict:
    now = datetime.now(timezone.utc)
    midnight = datetime.now(PARIS).replace(hour=0, minute=0, second=0, microsecond=0)
    bot = await bot_get("/status")
    online = bool(isinstance(bot, dict) and bot.get("ready"))
    failed: list = []
    payload = {
        "online": online,
        "latency_ms": _latency(bot) if online else None,
        "availability": await _safe(failed, "disponibilité", lambda: _availability(now),
                                    {"percent": None, "since": None}),
        "commands_served": await _safe(failed, "commandes", lambda: _count(
            "SELECT COALESCE(SUM(usage_count), 0) FROM user_command_stats")),
        "today": {
            # Aucune table ne journalise l'XP distribuée ni les rappels de bump envoyés
            # (bump_reminder_state = une seule ligne, réécrite à chaque bump) : jamais inventés.
            "xp_distributed": None,
            "achievements": await _safe(failed, "succès", lambda: _count(
                "SELECT COUNT(*) FROM user_achievements WHERE unlocked_at >= $1", midnight)),
            "tickets": await _safe(failed, "tickets", lambda: _count(
                "SELECT COUNT(*) FROM tickets WHERE created_at >= $1", midnight)),
            "bump_reminders": None,
        },
        "daily_curve": await _safe(failed, "courbe", lambda: _curve(now), []),
    }
    if failed:
        raise _Degraded(payload)
    return payload


@router.get("/hermes/status")
@limiter.limit("60/minute")
async def get_status(request: Request):
    global _last_good
    try:
        payload = await cached("hermes-status", STATUS_TTL, _build_status)
    except _Degraded as degraded:
        # Requête SQL en échec : dernières bonnes valeurs si on les a, sinon le partiel (valeurs None).
        return {**(_last_good or degraded.payload), "stale": True}
    except Exception:
        log.exception("Statut Hermes : construction impossible")
        payload = None
    if payload is None:
        if _last_good is not None:
            return {**_last_good, "stale": True}
        return {"online": False, "latency_ms": None, "availability": {"percent": None, "since": None},
                "commands_served": None,
                "today": {"xp_distributed": None, "achievements": None, "tickets": None,
                          "bump_reminders": None},
                "daily_curve": [], "stale": True}
    _last_good = payload
    return payload
