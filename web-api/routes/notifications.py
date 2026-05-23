from fastapi import APIRouter, Depends
from middleware.auth_middleware import get_current_user
import database as db

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
async def get_notifications(user: dict = Depends(get_current_user)):
    rows = await db.fetch(
        "SELECT * FROM user_notifications WHERE user_id = $1 ORDER BY created_at DESC LIMIT 50",
        int(user['sub'])
    )
    return {"notifications": [dict(r) for r in rows]}


@router.post("/{notif_id}/read")
async def mark_read(notif_id: int, user: dict = Depends(get_current_user)):
    await db.execute(
        "UPDATE user_notifications SET is_read = TRUE WHERE id = $1 AND user_id = $2",
        notif_id, int(user['sub'])
    )
    return {"success": True}


@router.post("/read-all")
async def mark_all_read(user: dict = Depends(get_current_user)):
    await db.execute(
        "UPDATE user_notifications SET is_read = TRUE WHERE user_id = $1", int(user['sub'])
    )
    return {"success": True}
