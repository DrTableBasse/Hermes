from fastapi import APIRouter
import database as db

router = APIRouter(prefix="/xp", tags=["xp"])


@router.get("/leaderboard")
async def xp_leaderboard(limit: int = 10, period: str = "all"):
    limit = max(1, min(limit, 100))
    if period == "weekly":
        rows = await db.fetch(
            "SELECT x.user_id, x.total_xp, x.weekly_xp, x.current_level, v.username, v.discord_avatar "
            "FROM user_xp x JOIN user_voice_data v ON x.user_id = v.user_id "
            "ORDER BY x.weekly_xp DESC LIMIT $1",
            limit,
        )
    else:
        rows = await db.fetch(
            "SELECT x.user_id, x.total_xp, x.weekly_xp, x.current_level, v.username, v.discord_avatar "
            "FROM user_xp x JOIN user_voice_data v ON x.user_id = v.user_id "
            "ORDER BY x.total_xp DESC LIMIT $1",
            limit,
        )
    return {"leaderboard": [dict(r) for r in rows]}


@router.get("/{user_id}")
async def get_user_xp(user_id: int):
    row = await db.fetchrow("SELECT * FROM user_xp WHERE user_id = $1", user_id)
    if not row:
        return {"user_id": user_id, "total_xp": 0, "weekly_xp": 0, "current_level": 0}
    return dict(row)
