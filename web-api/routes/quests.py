from fastapi import APIRouter, Depends, HTTPException
from middleware.auth_middleware import get_current_user
import database as db

router = APIRouter(prefix="/quests", tags=["quests"])


@router.get("")
async def list_quests(user: dict = Depends(get_current_user)):
    user_id = int(user['sub'])
    rows = await db.fetch("""
        SELECT q.*, COALESCE(up.current_progress, 0) AS current_progress, COALESCE(up.status, 'active') AS status
        FROM weekly_quests q
        LEFT JOIN user_quest_progress up ON q.id = up.quest_id AND up.user_id = $1
        WHERE q.is_active = TRUE
        ORDER BY q.id
    """, user_id)
    return {"quests": [dict(r) for r in rows]}


@router.post("/{quest_id}/claim")
async def claim_quest(quest_id: int, user: dict = Depends(get_current_user)):
    user_id = int(user['sub'])
    progress = await db.fetchrow(
        "SELECT * FROM user_quest_progress WHERE quest_id=$1 AND user_id=$2", quest_id, user_id
    )
    if not progress or progress['status'] != 'completed':
        raise HTTPException(400, "Ce défi n'est pas encore complété")
    quest = await db.fetchrow("SELECT * FROM weekly_quests WHERE id=$1", quest_id)
    if not quest:
        raise HTTPException(404, "Défi introuvable")
    await db.execute(
        "UPDATE user_quest_progress SET status='claimed' WHERE quest_id=$1 AND user_id=$2",
        quest_id, user_id
    )
    return {"success": True, "xp_reward": quest['xp_reward']}
