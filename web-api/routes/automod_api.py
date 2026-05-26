from fastapi import APIRouter, Depends
from middleware.auth_middleware import get_current_user, require_admin
import database as db

router = APIRouter(prefix="/automod", tags=["automod"])


@router.get("/logs")
async def get_automod_logs(limit: int = 50, user: dict = Depends(get_current_user)):
    require_admin(user)
    limit = max(1, min(limit, 200))
    rows = await db.fetch(
        "SELECT * FROM automod_logs ORDER BY created_at DESC LIMIT $1", limit
    )
    return {"logs": [dict(r) for r in rows]}


@router.get("/config/{guild_id}")
async def get_config(guild_id: int, user: dict = Depends(get_current_user)):
    require_admin(user)
    row = await db.fetchrow("SELECT * FROM automod_config WHERE guild_id=$1", guild_id)
    return dict(row) if row else {}
