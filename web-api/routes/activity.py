from fastapi import APIRouter
import database as db
from datetime import date, timedelta

router = APIRouter(prefix="/activity", tags=["activity"])


@router.get("/{user_id}/heatmap")
async def activity_heatmap(user_id: int, days: int = 365):
    days = max(7, min(days, 365))
    since = date.today() - timedelta(days=days)
    rows = await db.fetch("""
        SELECT date_trunc('day', created_at)::date AS day, COUNT(*) AS count
        FROM user_message_stats
        WHERE user_id = $1 AND created_at >= $2
        GROUP BY day ORDER BY day
    """, user_id, since)
    return {"heatmap": [{"date": str(r['day']), "count": int(r['count'])} for r in rows]}


@router.get("/{user_id}/daily")
async def daily_activity(user_id: int, days: int = 30):
    days = max(1, min(days, 90))
    since = date.today() - timedelta(days=days)
    msg_rows = await db.fetch("""
        SELECT date_trunc('day', created_at)::date AS day, SUM(message_count)::int AS messages
        FROM user_message_stats WHERE user_id=$1 AND created_at >= $2
        GROUP BY day ORDER BY day
    """, user_id, since)
    return {"daily": [{"date": str(r['day']), "messages": r['messages']} for r in msg_rows]}
