from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from middleware.auth_middleware import get_current_user
import database as db

router = APIRouter(prefix="/endorsements", tags=["endorsements"])


class EndorseInput(BaseModel):
    target_user_id: int
    skill: str


@router.post("")
async def endorse(body: EndorseInput, user: dict = Depends(get_current_user)):
    sender_id = int(user['sub'])
    if sender_id == body.target_user_id:
        raise HTTPException(400, "Impossible de s'endosser soi-même")
    exists = await db.fetchval("""
        SELECT id FROM endorsements
        WHERE sender_id=$1 AND receiver_id=$2 AND skill=$3
          AND created_at > NOW() - INTERVAL '24 hours'
    """, sender_id, body.target_user_id, body.skill)
    if exists:
        raise HTTPException(429, "Déjà endorsé aujourd'hui pour cette compétence")
    await db.execute(
        "INSERT INTO endorsements (sender_id, receiver_id, skill) VALUES ($1, $2, $3)",
        sender_id, body.target_user_id, body.skill
    )
    await db.execute("""
        INSERT INTO user_reputation (user_id, total_endorsements, last_endorsement_at)
        VALUES ($1, 1, NOW())
        ON CONFLICT (user_id) DO UPDATE
          SET total_endorsements = user_reputation.total_endorsements + 1,
              last_endorsement_at = NOW()
    """, body.target_user_id)
    return {"success": True}


@router.get("/{user_id}")
async def get_endorsements(user_id: int):
    rows = await db.fetch(
        "SELECT skill, COUNT(*) as count FROM endorsements WHERE receiver_id=$1 GROUP BY skill ORDER BY count DESC",
        user_id
    )
    rep = await db.fetchrow("SELECT * FROM user_reputation WHERE user_id=$1", user_id)
    return {
        "skills": [dict(r) for r in rows],
        "total": rep['total_endorsements'] if rep else 0,
    }


@router.get("")
async def reputation_leaderboard(limit: int = 10):
    limit = max(1, min(limit, 100))
    rows = await db.fetch("""
        SELECT r.user_id, r.total_endorsements, v.username, v.discord_avatar
        FROM user_reputation r
        JOIN user_voice_data v ON r.user_id = v.user_id
        ORDER BY r.total_endorsements DESC LIMIT $1
    """, limit)
    return {"leaderboard": [dict(r) for r in rows]}
