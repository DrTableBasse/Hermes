from fastapi import APIRouter, Cookie, Depends, HTTPException
from auth import decode_jwt
from middleware.auth_middleware import get_current_user
import database as db

router = APIRouter(prefix="/users", tags=["users"])


async def _check_achievements(user_id: int, total_messages: int, voice_hours: float, warn_count: int):
    """Unlock achievements the user has earned but not yet received."""
    achievements = await db.fetch("SELECT * FROM achievements")
    unlocked_ids = {r['achievement_id'] for r in
                    await db.fetch("SELECT achievement_id FROM user_achievements WHERE user_id = $1", user_id)}

    for a in achievements:
        if a['id'] in unlocked_ids:
            continue
        ct  = a['condition_type']
        val = a['condition_value']
        earned = (
            (ct == 'messages'    and total_messages >= val) or
            (ct == 'voice_hours' and voice_hours    >= val) or
            (ct == 'warn_free'   and warn_count     == 0)
        )
        if earned:
            await db.execute(
                "INSERT INTO user_achievements (user_id, achievement_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                user_id, a['id']
            )


@router.get("/{user_id}/stats")
async def get_user_stats(user_id: int, token: str | None = Cookie(None, alias="hermes_token")):
    if not token or not decode_jwt(token):
        raise HTTPException(status_code=401, detail="Non authentifié")

    user = await db.fetchrow("SELECT * FROM user_voice_data WHERE user_id = $1", user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    total_messages = await db.fetchval(
        "SELECT COALESCE(SUM(message_count), 0) FROM user_message_stats WHERE user_id = $1", user_id
    ) or 0

    voice_hours = round((user['total_time'] or 0) / 3600, 2)
    warn_count  = await db.fetchval("SELECT COUNT(*) FROM warn WHERE user_id = $1", user_id) or 0

    # Compute rankings
    msg_rank = await db.fetchval("""
        SELECT COUNT(*) + 1 FROM (
            SELECT user_id, SUM(message_count) AS total
            FROM user_message_stats GROUP BY user_id
        ) t WHERE t.total > $1
    """, total_messages)

    voice_rank = await db.fetchval(
        "SELECT COUNT(*) + 1 FROM user_voice_data WHERE total_time > $1", user['total_time'] or 0
    )

    # Check + unlock achievements
    await _check_achievements(user_id, total_messages, voice_hours, warn_count)

    achievements = await db.fetch("""
        SELECT a.*, ua.unlocked_at
        FROM achievements a
        JOIN user_achievements ua ON a.id = ua.achievement_id
        WHERE ua.user_id = $1
        ORDER BY ua.unlocked_at DESC
    """, user_id)

    return {
        "user": {
            "user_id":        user_id,
            "username":       user['username'],
            "nickname":       user['nickname'],
            "discord_avatar": user['discord_avatar'],
            "last_seen":      user['last_seen'],
        },
        "stats": {
            "total_messages": int(total_messages),
            "voice_hours":    voice_hours,
            "warn_count":     int(warn_count),
            "msg_rank":       int(msg_rank or 1),
            "voice_rank":     int(voice_rank or 1),
        },
        "achievements": [
            {
                "id":          a['id'],
                "name":        a['name'],
                "description": a['description'],
                "icon":        a['icon'],
                "points":      a['points'],
                "unlocked_at": a['unlocked_at'],
            }
            for a in achievements
        ],
    }
