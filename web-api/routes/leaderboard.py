from fastapi import APIRouter
import database as db

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])


@router.get("/messages")
async def leaderboard_messages(limit: int = 10):
    rows = await db.fetch("""
        SELECT u.user_id, u.username, u.discord_avatar,
               SUM(s.message_count) AS total_messages
        FROM user_voice_data u
        JOIN user_message_stats s ON u.user_id = s.user_id
        GROUP BY u.user_id, u.username, u.discord_avatar
        ORDER BY total_messages DESC
        LIMIT $1
    """, min(limit, 100))
    return {"leaderboard": [dict(r) for r in rows]}


@router.get("/voice")
async def leaderboard_voice(limit: int = 10):
    rows = await db.fetch("""
        SELECT user_id, username, discord_avatar, total_time
        FROM user_voice_data
        ORDER BY total_time DESC
        LIMIT $1
    """, min(limit, 100))
    result = []
    for r in rows:
        s = r['total_time'] or 0
        h, rem = divmod(s, 3600)
        m, _   = divmod(rem, 60)
        result.append({
            "user_id":        r['user_id'],
            "username":       r['username'],
            "discord_avatar": r['discord_avatar'],
            "total_seconds":  s,
            "formatted":      f"{h}h {m}m",
        })
    return {"leaderboard": result}
