from typing import Optional
from fastapi import APIRouter, Depends
import database as db
from middleware.auth_middleware import get_current_user

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])


@router.get("/voice")
async def leaderboard_voice(page: int = 1, limit: int = 10, search: Optional[str] = None):
    limit  = max(1, min(limit, 100))
    page   = max(1, page)
    offset = (page - 1) * limit

    if search:
        pattern = f"%{search}%"
        total = await db.fetchval(
            "SELECT COUNT(*) FROM user_voice_data WHERE username ILIKE $1", pattern
        )
        rows = await db.fetch("""
            SELECT * FROM (
                SELECT user_id, username, discord_avatar, total_time,
                       RANK() OVER (ORDER BY total_time DESC) AS global_rank
                FROM user_voice_data
            ) ranked
            WHERE username ILIKE $1
            ORDER BY global_rank
            LIMIT $2 OFFSET $3
        """, pattern, limit, offset)
    else:
        total = await db.fetchval("SELECT COUNT(*) FROM user_voice_data")
        rows  = await db.fetch("""
            SELECT user_id, username, discord_avatar, total_time,
                   RANK() OVER (ORDER BY total_time DESC) AS global_rank
            FROM user_voice_data
            ORDER BY global_rank
            LIMIT $1 OFFSET $2
        """, limit, offset)

    result = []
    for r in rows:
        s = r['total_time'] or 0
        h, rem = divmod(s, 3600)
        m, _   = divmod(rem, 60)
        result.append({
            "user_id":        str(r['user_id']),
            "username":       r['username'],
            "discord_avatar": r['discord_avatar'],
            "total_seconds":  s,
            "formatted":      f"{h}h {m}m",
            "global_rank":    int(r['global_rank']),
        })
    return {"leaderboard": result, "total": int(total or 0), "page": page, "limit": limit}


@router.get("/messages")
async def leaderboard_messages(page: int = 1, limit: int = 10, search: Optional[str] = None):
    limit  = max(1, min(limit, 100))
    page   = max(1, page)
    offset = (page - 1) * limit

    if search:
        pattern = f"%{search}%"
        total = await db.fetchval(
            "SELECT COUNT(*) FROM user_voice_data WHERE username ILIKE $1", pattern
        )
        rows = await db.fetch("""
            SELECT * FROM (
                SELECT u.user_id, u.username, u.discord_avatar,
                       COALESCE(SUM(s.message_count), 0) AS total_messages,
                       RANK() OVER (ORDER BY COALESCE(SUM(s.message_count), 0) DESC) AS global_rank
                FROM user_voice_data u
                LEFT JOIN user_message_stats s ON u.user_id = s.user_id
                GROUP BY u.user_id, u.username, u.discord_avatar
            ) ranked
            WHERE username ILIKE $1
            ORDER BY global_rank
            LIMIT $2 OFFSET $3
        """, pattern, limit, offset)
    else:
        total = await db.fetchval("SELECT COUNT(*) FROM user_voice_data")
        rows  = await db.fetch("""
            SELECT u.user_id, u.username, u.discord_avatar,
                   COALESCE(SUM(s.message_count), 0) AS total_messages,
                   RANK() OVER (ORDER BY COALESCE(SUM(s.message_count), 0) DESC) AS global_rank
            FROM user_voice_data u
            LEFT JOIN user_message_stats s ON u.user_id = s.user_id
            GROUP BY u.user_id, u.username, u.discord_avatar
            ORDER BY global_rank
            LIMIT $1 OFFSET $2
        """, limit, offset)

    return {
        "leaderboard": [
            {**dict(r), "user_id": str(r["user_id"]),
             "total_messages": int(r["total_messages"]), "global_rank": int(r["global_rank"])}
            for r in rows
        ],
        "total": int(total or 0),
        "page": page,
        "limit": limit,
    }


@router.get("/achievements")
async def leaderboard_achievements(page: int = 1, limit: int = 10, search: Optional[str] = None):
    limit  = max(1, min(limit, 100))
    page   = max(1, page)
    offset = (page - 1) * limit

    if search:
        pattern = f"%{search}%"
        total = await db.fetchval(
            "SELECT COUNT(*) FROM user_voice_data WHERE username ILIKE $1", pattern
        )
        rows = await db.fetch("""
            SELECT * FROM (
                SELECT v.user_id, v.username, v.discord_avatar,
                       COUNT(ua.achievement_id) AS achievement_count,
                       RANK() OVER (ORDER BY COUNT(ua.achievement_id) DESC) AS global_rank
                FROM user_voice_data v
                LEFT JOIN user_achievements ua ON v.user_id = ua.user_id
                GROUP BY v.user_id, v.username, v.discord_avatar
            ) ranked
            WHERE username ILIKE $1
            ORDER BY global_rank
            LIMIT $2 OFFSET $3
        """, pattern, limit, offset)
    else:
        total = await db.fetchval("SELECT COUNT(*) FROM user_voice_data")
        rows  = await db.fetch("""
            SELECT v.user_id, v.username, v.discord_avatar,
                   COUNT(ua.achievement_id) AS achievement_count,
                   RANK() OVER (ORDER BY COUNT(ua.achievement_id) DESC) AS global_rank
            FROM user_voice_data v
            LEFT JOIN user_achievements ua ON v.user_id = ua.user_id
            GROUP BY v.user_id, v.username, v.discord_avatar
            ORDER BY global_rank
            LIMIT $1 OFFSET $2
        """, limit, offset)

    return {
        "leaderboard": [
            {**dict(r), "user_id": str(r["user_id"]),
             "achievement_count": int(r["achievement_count"]), "global_rank": int(r["global_rank"])}
            for r in rows
        ],
        "total": int(total or 0),
        "page": page,
        "limit": limit,
    }


@router.get("/xp")
async def leaderboard_xp(page: int = 1, limit: int = 10, period: str = "all"):
    limit  = max(1, min(limit, 100))
    page   = max(1, page)
    offset = (page - 1) * limit

    total = await db.fetchval("SELECT COUNT(*) FROM user_xp")
    if period == "weekly":
        rows = await db.fetch(
            "SELECT x.user_id, x.total_xp, x.weekly_xp, x.current_level, v.username, v.discord_avatar "
            "FROM user_xp x JOIN user_voice_data v ON x.user_id = v.user_id "
            "ORDER BY x.weekly_xp DESC LIMIT $1 OFFSET $2",
            limit, offset,
        )
    else:
        rows = await db.fetch(
            "SELECT x.user_id, x.total_xp, x.weekly_xp, x.current_level, v.username, v.discord_avatar "
            "FROM user_xp x JOIN user_voice_data v ON x.user_id = v.user_id "
            "ORDER BY x.total_xp DESC LIMIT $1 OFFSET $2",
            limit, offset,
        )
    return {"leaderboard": [dict(r) for r in rows], "total": int(total or 0), "page": page, "limit": limit}


@router.get("/global")
async def leaderboard_global(page: int = 1, limit: int = 10):
    """Combined score: 1pt/min voice + 1pt/message + 200pt/achievement."""
    limit  = max(1, min(limit, 100))
    page   = max(1, page)
    offset = (page - 1) * limit

    total = await db.fetchval("SELECT COUNT(*) FROM user_voice_data")
    rows  = await db.fetch("""
        SELECT
            v.user_id, v.username, v.discord_avatar,
            COALESCE(v.total_time / 60, 0)          AS voice_minutes,
            COALESCE(msg.total_messages, 0)          AS total_messages,
            COALESCE(ach.achievement_count, 0)       AS achievement_count,
            COALESCE(v.total_time / 60, 0)
              + COALESCE(msg.total_messages, 0)
              + COALESCE(ach.achievement_count * 200, 0) AS global_score
        FROM user_voice_data v
        LEFT JOIN (
            SELECT user_id, SUM(message_count) AS total_messages
            FROM user_message_stats GROUP BY user_id
        ) msg ON v.user_id = msg.user_id
        LEFT JOIN (
            SELECT user_id, COUNT(*) AS achievement_count
            FROM user_achievements GROUP BY user_id
        ) ach ON v.user_id = ach.user_id
        ORDER BY global_score DESC
        LIMIT $1 OFFSET $2
    """, limit, offset)

    result = []
    for r in rows:
        vm = int(r['voice_minutes'])
        result.append({
            "user_id":           str(r['user_id']),
            "username":          r['username'],
            "discord_avatar":    r['discord_avatar'],
            "voice_formatted":   f"{vm // 60}h {vm % 60}m",
            "total_messages":    int(r['total_messages']),
            "achievement_count": int(r['achievement_count']),
            "global_score":      int(r['global_score']),
        })
    return {"leaderboard": result, "total": int(total or 0), "page": page, "limit": limit}


@router.get("/bumps")
async def leaderboard_bumps(page: int = 1, limit: int = 10, search: Optional[str] = None):
    limit  = max(1, min(limit, 100))
    page   = max(1, page)
    offset = (page - 1) * limit

    if search:
        pattern = f"%{search}%"
        total = await db.fetchval(
            "SELECT COUNT(*) FROM user_voice_data WHERE username ILIKE $1", pattern
        )
        rows = await db.fetch("""
            SELECT * FROM (
                SELECT u.user_id, u.username, u.discord_avatar,
                       COALESCE(b.bump_count, 0) AS bump_count,
                       RANK() OVER (ORDER BY COALESCE(b.bump_count, 0) DESC) AS global_rank
                FROM user_voice_data u
                LEFT JOIN user_bump_stats b ON u.user_id = b.user_id
            ) ranked
            WHERE username ILIKE $1
            ORDER BY global_rank
            LIMIT $2 OFFSET $3
        """, pattern, limit, offset)
    else:
        total = await db.fetchval("SELECT COUNT(*) FROM user_voice_data")
        rows  = await db.fetch("""
            SELECT u.user_id, u.username, u.discord_avatar,
                   COALESCE(b.bump_count, 0) AS bump_count,
                   RANK() OVER (ORDER BY COALESCE(b.bump_count, 0) DESC) AS global_rank
            FROM user_voice_data u
            LEFT JOIN user_bump_stats b ON u.user_id = b.user_id
            ORDER BY global_rank
            LIMIT $1 OFFSET $2
        """, limit, offset)

    return {
        "leaderboard": [
            {**dict(r), "user_id": str(r["user_id"]),
             "bump_count": int(r["bump_count"]), "global_rank": int(r["global_rank"])}
            for r in rows
        ],
        "total": int(total or 0),
        "page": page,
        "limit": limit,
    }


@router.get("/invites")
async def leaderboard_invites(page: int = 1, limit: int = 10, search: Optional[str] = None):
    limit  = max(1, min(limit, 100))
    page   = max(1, page)
    offset = (page - 1) * limit

    if search:
        pattern = f"%{search}%"
        total = await db.fetchval(
            "SELECT COUNT(*) FROM user_voice_data WHERE username ILIKE $1", pattern
        )
        rows = await db.fetch("""
            SELECT * FROM (
                SELECT u.user_id, u.username, u.discord_avatar,
                       COALESCE(i.invite_count, 0) AS invite_count,
                       RANK() OVER (ORDER BY COALESCE(i.invite_count, 0) DESC) AS global_rank
                FROM user_voice_data u
                LEFT JOIN user_invite_stats i ON u.user_id = i.user_id
            ) ranked
            WHERE username ILIKE $1
            ORDER BY global_rank
            LIMIT $2 OFFSET $3
        """, pattern, limit, offset)
    else:
        total = await db.fetchval("SELECT COUNT(*) FROM user_voice_data")
        rows  = await db.fetch("""
            SELECT u.user_id, u.username, u.discord_avatar,
                   COALESCE(i.invite_count, 0) AS invite_count,
                   RANK() OVER (ORDER BY COALESCE(i.invite_count, 0) DESC) AS global_rank
            FROM user_voice_data u
            LEFT JOIN user_invite_stats i ON u.user_id = i.user_id
            ORDER BY global_rank
            LIMIT $1 OFFSET $2
        """, limit, offset)

    return {
        "leaderboard": [
            {**dict(r), "user_id": str(r["user_id"]),
             "invite_count": int(r["invite_count"]), "global_rank": int(r["global_rank"])}
            for r in rows
        ],
        "total": int(total or 0),
        "page": page,
        "limit": limit,
    }


@router.get("/levels")
async def leaderboard_levels(page: int = 1, limit: int = 10, search: Optional[str] = None):
    limit  = max(1, min(limit, 100))
    page   = max(1, page)
    offset = (page - 1) * limit

    if search:
        pattern = f"%{search}%"
        total = await db.fetchval(
            "SELECT COUNT(*) FROM user_xp x JOIN user_voice_data v ON x.user_id = v.user_id WHERE v.username ILIKE $1",
            pattern,
        )
        rows = await db.fetch("""
            SELECT * FROM (
                SELECT v.user_id, v.username, v.discord_avatar,
                       x.current_level, x.total_xp,
                       RANK() OVER (ORDER BY x.current_level DESC, x.total_xp DESC) AS global_rank
                FROM user_xp x JOIN user_voice_data v ON x.user_id = v.user_id
            ) ranked
            WHERE username ILIKE $1
            ORDER BY global_rank
            LIMIT $2 OFFSET $3
        """, pattern, limit, offset)
    else:
        total = await db.fetchval("SELECT COUNT(*) FROM user_xp")
        rows  = await db.fetch("""
            SELECT v.user_id, v.username, v.discord_avatar,
                   x.current_level, x.total_xp,
                   RANK() OVER (ORDER BY x.current_level DESC, x.total_xp DESC) AS global_rank
            FROM user_xp x JOIN user_voice_data v ON x.user_id = v.user_id
            ORDER BY global_rank
            LIMIT $1 OFFSET $2
        """, limit, offset)

    return {
        "leaderboard": [
            {
                "user_id":        str(r["user_id"]),
                "username":       r["username"],
                "discord_avatar": r["discord_avatar"],
                "current_level":  int(r["current_level"]),
                "total_xp":       int(r["total_xp"]),
                "global_rank":    int(r["global_rank"]),
            }
            for r in rows
        ],
        "total": int(total or 0),
        "page":  page,
        "limit": limit,
    }


@router.get("/streaks")
async def leaderboard_streaks(page: int = 1, limit: int = 10, search: Optional[str] = None):
    limit  = max(1, min(limit, 100))
    page   = max(1, page)
    offset = (page - 1) * limit

    if search:
        pattern = f"%{search}%"
        total = await db.fetchval(
            "SELECT COUNT(*) FROM user_voice_data WHERE username ILIKE $1", pattern
        )
        rows = await db.fetch("""
            SELECT * FROM (
                SELECT v.user_id, v.username, v.discord_avatar,
                       COALESCE(s.current_streak, 0) AS current_streak,
                       COALESCE(s.max_streak, 0)     AS max_streak,
                       COALESCE(s.xp_multiplier, 1)  AS xp_multiplier,
                       RANK() OVER (ORDER BY COALESCE(s.current_streak, 0) DESC) AS global_rank
                FROM user_voice_data v
                LEFT JOIN user_streaks s ON v.user_id = s.user_id
            ) ranked
            WHERE username ILIKE $1
            ORDER BY global_rank
            LIMIT $2 OFFSET $3
        """, pattern, limit, offset)
    else:
        total = await db.fetchval("SELECT COUNT(*) FROM user_voice_data")
        rows  = await db.fetch("""
            SELECT v.user_id, v.username, v.discord_avatar,
                   COALESCE(s.current_streak, 0) AS current_streak,
                   COALESCE(s.max_streak, 0)     AS max_streak,
                   COALESCE(s.xp_multiplier, 1)  AS xp_multiplier,
                   RANK() OVER (ORDER BY COALESCE(s.current_streak, 0) DESC) AS global_rank
            FROM user_voice_data v
            LEFT JOIN user_streaks s ON v.user_id = s.user_id
            ORDER BY global_rank
            LIMIT $1 OFFSET $2
        """, limit, offset)

    return {
        "leaderboard": [
            {
                "user_id":        str(r["user_id"]),
                "username":       r["username"],
                "discord_avatar": r["discord_avatar"],
                "current_streak": int(r["current_streak"]),
                "max_streak":     int(r["max_streak"]),
                "xp_multiplier":  float(r["xp_multiplier"]),
                "global_rank":    int(r["global_rank"]),
            }
            for r in rows
        ],
        "total": int(total or 0),
        "page":  page,
        "limit": limit,
    }


@router.get("/me")
async def my_ranks(user: dict = Depends(get_current_user)):
    uid = int(user['sub'])

    voice_rank = await db.fetchval("""
        SELECT COUNT(*) + 1 FROM user_voice_data
        WHERE total_time > COALESCE((SELECT total_time FROM user_voice_data WHERE user_id = $1), 0)
    """, uid)

    msg_rank = await db.fetchval("""
        SELECT COUNT(*) + 1 FROM (
            SELECT user_id, SUM(message_count) AS total FROM user_message_stats GROUP BY user_id
        ) t WHERE total > COALESCE(
            (SELECT SUM(message_count) FROM user_message_stats WHERE user_id = $1), 0
        )
    """, uid)

    ach_rank = await db.fetchval("""
        SELECT COUNT(*) + 1 FROM (
            SELECT user_id, COUNT(*) AS cnt FROM user_achievements GROUP BY user_id
        ) t WHERE cnt > COALESCE(
            (SELECT COUNT(*) FROM user_achievements WHERE user_id = $1), 0
        )
    """, uid)

    bump_rank = await db.fetchval("""
        SELECT COUNT(*) + 1 FROM user_bump_stats
        WHERE bump_count > COALESCE((SELECT bump_count FROM user_bump_stats WHERE user_id = $1), 0)
    """, uid)

    invite_rank = await db.fetchval("""
        SELECT COUNT(*) + 1 FROM user_invite_stats
        WHERE invite_count > COALESCE((SELECT invite_count FROM user_invite_stats WHERE user_id = $1), 0)
    """, uid)

    level_rank = await db.fetchval("""
        SELECT COUNT(*) + 1 FROM user_xp
        WHERE current_level > COALESCE((SELECT current_level FROM user_xp WHERE user_id = $1), 0)
           OR (current_level = COALESCE((SELECT current_level FROM user_xp WHERE user_id = $1), 0)
               AND total_xp > COALESCE((SELECT total_xp FROM user_xp WHERE user_id = $1), 0))
    """, uid)

    streak_rank = await db.fetchval("""
        SELECT COUNT(*) + 1 FROM user_streaks
        WHERE current_streak > COALESCE((SELECT current_streak FROM user_streaks WHERE user_id = $1), 0)
    """, uid)

    return {
        "voice_rank":        int(voice_rank or 1),
        "messages_rank":     int(msg_rank or 1),
        "achievements_rank": int(ach_rank or 1),
        "bumps_rank":        int(bump_rank or 1),
        "invites_rank":      int(invite_rank or 1),
        "level_rank":        int(level_rank or 1),
        "streak_rank":       int(streak_rank or 1),
    }
