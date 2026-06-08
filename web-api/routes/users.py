import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request
from limiter import limiter
from middleware.auth_middleware import get_current_user
import database as db

router = APIRouter(prefix="/users", tags=["users"])


async def _check_achievements(user_id: int, total_messages: int, voice_hours: float, warn_count: int):
    achievements = await db.fetch("SELECT * FROM achievements")
    unlocked_ids = {r['achievement_id'] for r in
                    await db.fetch("SELECT achievement_id FROM user_achievements WHERE user_id = $1", user_id)}

    xp_data        = await db.fetchrow("SELECT * FROM user_xp WHERE user_id = $1", user_id)
    streak_data    = await db.fetchrow("SELECT * FROM user_streaks WHERE user_id = $1", user_id)
    msg_streak_data= await db.fetchrow("SELECT * FROM user_message_streaks WHERE user_id = $1", user_id)
    rep_data       = await db.fetchrow("SELECT * FROM user_reputation WHERE user_id = $1", user_id)
    voice_data     = await db.fetchrow("SELECT * FROM user_voice_data WHERE user_id = $1", user_id)

    quests_completed = await db.fetchval(
        "SELECT COUNT(*) FROM user_quest_progress WHERE user_id = $1 AND xp_claimed = TRUE", user_id
    ) or 0
    articles_written = await db.fetchval(
        "SELECT COUNT(*) FROM articles WHERE author_id = $1 AND published = TRUE", user_id
    ) or 0
    comments_posted = await db.fetchval(
        "SELECT COUNT(*) FROM article_comments WHERE user_id = $1", user_id
    ) or 0
    votes_cast = await db.fetchval(
        "SELECT COUNT(*) FROM article_votes WHERE user_id = $1", user_id
    ) or 0
    commands_used = await db.fetchval(
        "SELECT COALESCE(SUM(usage_count), 0) FROM user_command_stats WHERE user_id = $1", user_id
    ) or 0
    blague_count = await db.fetchval(
        "SELECT COALESCE(usage_count, 0) FROM user_command_stats WHERE user_id = $1 AND command_name = 'blague'", user_id
    ) or 0
    confess_count = await db.fetchval(
        "SELECT COALESCE(usage_count, 0) FROM user_command_stats WHERE user_id = $1 AND command_name = 'confess'", user_id
    ) or 0
    bump_count = await db.fetchval(
        "SELECT COALESCE(bump_count, 0) FROM user_bump_stats WHERE user_id = $1", user_id
    ) or 0
    invite_count = await db.fetchval(
        "SELECT COALESCE(invite_count, 0) FROM user_invite_stats WHERE user_id = $1", user_id
    ) or 0
    distinct_channels = await db.fetchval(
        "SELECT COUNT(DISTINCT channel_id) FROM user_message_stats WHERE user_id = $1", user_id
    ) or 0
    days_on_server = await db.fetchval(
        "SELECT EXTRACT(DAY FROM NOW() - created_at)::int FROM user_voice_data WHERE user_id = $1", user_id
    ) or 0
    warn_free_days = await db.fetchval(
        """SELECT EXTRACT(DAY FROM NOW() - COALESCE(
            TO_TIMESTAMP(MAX(create_time)),
            (SELECT created_at FROM user_voice_data WHERE user_id = $1)
           ))::int FROM warn WHERE user_id = $1""", user_id
    )
    if warn_free_days is None:
        warn_free_days = days_on_server  # no warns ever

    voice_streak = int(streak_data['current_streak']) if streak_data and streak_data.get('current_streak') else 0
    msg_streak   = int(msg_streak_data['current_streak']) if msg_streak_data and msg_streak_data.get('current_streak') else 0
    msg_max_streak = int(msg_streak_data['max_streak']) if msg_streak_data and msg_streak_data.get('max_streak') else 0
    current_streak = max(voice_streak, msg_streak)

    vd = voice_data or {}

    for a in achievements:
        if a['id'] in unlocked_ids:
            continue
        ct  = a['condition_type']
        val = a['condition_value']

        if ct == 'custom':
            continue

        if   ct == 'messages':
            earned = total_messages >= val
        elif ct == 'voice_hours':
            earned = voice_hours >= val
        elif ct == 'warn_free':
            earned = warn_count == 0
        elif ct in ('xp_total',):
            earned = int(xp_data['total_xp']) >= val if xp_data else False
        elif ct == 'level':
            earned = int(xp_data['current_level']) >= val if xp_data else False
        elif ct == 'streak_days':
            earned = current_streak >= val
        elif ct == 'message_streak_days':
            earned = max(msg_streak, msg_max_streak) >= val
        elif ct == 'quests_completed':
            earned = quests_completed >= val
        elif ct in ('unique_voice_channels',):
            earned = int(vd.get('unique_voice_channels_count') or 0) >= val
        elif ct == 'endorsements_received':
            earned = int(rep_data['total_count']) >= val if rep_data else False
        elif ct in ('voice_night_minutes', 'night_owl'):
            earned = int(vd.get('voice_night_minutes') or 0) >= val
        elif ct in ('voice_morning_minutes', 'early_bird'):
            earned = int(vd.get('voice_morning_minutes') or 0) >= val
        elif ct in ('longest_session_minutes', 'long_session'):
            earned = int(vd.get('longest_session_minutes') or 0) >= val
        elif ct in ('consecutive_voice_days', 'total_sessions'):
            earned = int(vd.get('consecutive_voice_days') or 0) >= val
        elif ct in ('articles_published', 'articles_written'):
            earned = articles_written >= val
        elif ct == 'comments_posted':
            earned = comments_posted >= val
        elif ct == 'votes_cast':
            earned = votes_cast >= val
        elif ct == 'commands_used':
            earned = commands_used >= val
        elif ct == 'blague_count':
            earned = blague_count >= val
        elif ct == 'confess_count':
            earned = confess_count >= val
        elif ct == 'bumps':
            earned = bump_count >= val
        elif ct == 'invites':
            earned = invite_count >= val
        elif ct == 'messages_multi_channel':
            earned = distinct_channels >= val
        elif ct == 'days_on_server':
            earned = days_on_server >= val
        elif ct in ('server_anniversary',):
            earned = days_on_server >= 365
        elif ct == 'warn_free_days':
            earned = int(warn_free_days or 0) >= val
        elif ct == 'reactions_given':
            earned = val == 0
        else:
            earned = False

        if earned:
            await db.execute(
                "INSERT INTO user_achievements (user_id, achievement_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                user_id, a['id']
            )


@router.get("/{user_id}/stats")
async def get_user_stats(user_id: int, _user: dict = Depends(get_current_user)):

    user = await db.fetchrow("SELECT * FROM user_voice_data WHERE user_id = $1", user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    total_messages = await db.fetchval(
        "SELECT COALESCE(SUM(message_count), 0) FROM user_message_stats WHERE user_id = $1", user_id
    ) or 0

    voice_hours = round((user['total_time'] or 0) / 3600, 2)
    warn_count = await db.fetchval("SELECT COUNT(*) FROM warn WHERE user_id = $1", user_id) or 0

    xp_data = await db.fetchrow("SELECT * FROM user_xp WHERE user_id = $1", user_id)
    streak_data = await db.fetchrow("SELECT * FROM user_streaks WHERE user_id = $1", user_id)
    msg_streak_data = await db.fetchrow("SELECT * FROM user_message_streaks WHERE user_id = $1", user_id)

    voice_streak = int(streak_data['current_streak']) if streak_data and streak_data.get('current_streak') else 0
    voice_max    = int(streak_data['max_streak'])     if streak_data and streak_data.get('max_streak')     else 0
    xp_multi     = float(streak_data['xp_multiplier']) if streak_data and streak_data.get('xp_multiplier') else 1.0
    current_streak = voice_streak
    msg_current  = int(msg_streak_data['current_streak']) if msg_streak_data and msg_streak_data.get('current_streak') else 0
    msg_max      = int(msg_streak_data['max_streak'])     if msg_streak_data and msg_streak_data.get('max_streak')     else 0

    msg_rank = await db.fetchval("""
        SELECT COUNT(*) + 1 FROM (
            SELECT user_id, SUM(message_count) AS total
            FROM user_message_stats GROUP BY user_id
        ) t WHERE t.total > $1
    """, total_messages)

    voice_rank = await db.fetchval(
        "SELECT COUNT(*) + 1 FROM user_voice_data WHERE total_time > $1", user['total_time'] or 0
    )

    bump_count = await db.fetchval(
        "SELECT COALESCE(bump_count, 0) FROM user_bump_stats WHERE user_id = $1", user_id
    ) or 0

    bump_rank = await db.fetchval("""
        SELECT COUNT(*) + 1 FROM user_bump_stats
        WHERE bump_count > COALESCE((SELECT bump_count FROM user_bump_stats WHERE user_id = $1), 0)
    """, user_id) or 1

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
            "xp_total":       int(xp_data['total_xp']) if xp_data else 0,
            "current_level":  int(xp_data['current_level']) if xp_data else 0,
            "current_streak": current_streak,
            "max_streak":     voice_max,
            "xp_multiplier":  xp_multi,
            "bump_count":         int(bump_count),
            "bump_rank":          int(bump_rank),
            "msg_current_streak": msg_current,
            "msg_max_streak":     msg_max,
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


@router.get("/{user_id}/public")
@limiter.limit("60/minute")
async def get_user_public_stats(request: Request, user_id: int):
    """Public stats — no auth required. Returns community-visible data only."""
    user = await db.fetchrow(
        "SELECT user_id, username, nickname, discord_avatar FROM user_voice_data WHERE user_id = $1",
        user_id,
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    total_messages, voice_row, xp_row, ach_count, streak_row, bump_count = await asyncio.gather(
        db.fetchval(
            "SELECT COALESCE(SUM(message_count), 0) FROM user_message_stats WHERE user_id = $1",
            user_id,
        ),
        db.fetchrow("SELECT total_time FROM user_voice_data WHERE user_id = $1", user_id),
        db.fetchrow("SELECT total_xp, current_level FROM user_xp WHERE user_id = $1", user_id),
        db.fetchval("SELECT COUNT(*) FROM user_achievements WHERE user_id = $1", user_id),
        db.fetchrow(
            "SELECT current_streak, max_streak FROM user_streaks WHERE user_id = $1", user_id
        ),
        db.fetchval(
            "SELECT COALESCE(bump_count, 0) FROM user_bump_stats WHERE user_id = $1", user_id
        ),
    )

    s = voice_row["total_time"] if voice_row else 0
    h, rem = divmod(s, 3600)
    m, _ = divmod(rem, 60)

    achievements = await db.fetch("""
        SELECT a.id, a.name, a.description, a.icon, a.points, ua.unlocked_at
        FROM achievements a
        JOIN user_achievements ua ON a.id = ua.achievement_id
        WHERE ua.user_id = $1
        ORDER BY a.points DESC, ua.unlocked_at DESC
    """, user_id)

    return {
        "user_id":        str(user_id),
        "username":       user["username"],
        "nickname":       user["nickname"],
        "discord_avatar": user["discord_avatar"],
        "stats": {
            "total_messages":    int(total_messages or 0),
            "voice_seconds":     s,
            "voice_formatted":   f"{h}h {m}m",
            "total_xp":          xp_row["total_xp"] if xp_row else 0,
            "current_level":     xp_row["current_level"] if xp_row else 0,
            "achievement_count": int(ach_count or 0),
            "current_streak":    streak_row["current_streak"] if streak_row else 0,
            "bump_count":        int(bump_count or 0),
        },
        "achievements": [
            {
                "id":          a["id"],
                "name":        a["name"],
                "description": a["description"],
                "icon":        a["icon"],
                "points":      a["points"],
                "unlocked_at": str(a["unlocked_at"]),
            }
            for a in achievements
        ],
    }
