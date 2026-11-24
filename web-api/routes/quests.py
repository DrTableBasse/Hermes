from datetime import date

from fastapi import APIRouter, Depends
from middleware.auth_middleware import get_current_user
import database as db

router = APIRouter(prefix="/quests", tags=["quests"])

# La récompense d'un défi est versée automatiquement par le bot dès qu'il est terminé :
# « completed » n'est donc qu'un état transitoire (quelques instants, ou bot hors ligne).
QUESTS_SQL = """
    SELECT q.id, q.title, q.description, q.quest_type, q.target_value, q.xp_reward, q.icon,
           q.week_start, q.week_end, q.is_active,
           LEAST(COALESCE(up.progress_value, 0), q.target_value) AS current_progress,
           CASE WHEN up.xp_claimed THEN 'claimed'
                WHEN up.completed THEN 'completed'
                ELSE 'active' END AS status
    FROM weekly_quests q
    LEFT JOIN user_quest_progress up ON q.id = up.quest_id AND up.user_id = $1
    WHERE q.is_active = TRUE AND q.week_end >= $2
    ORDER BY q.id
"""


@router.get("")
async def list_quests(user: dict = Depends(get_current_user)):
    rows = await db.fetch(QUESTS_SQL, int(user['sub']), date.today())
    return {"quests": [dict(r) for r in rows]}
