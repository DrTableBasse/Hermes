"""Admin routes — proxy to the bot's internal API."""
import os
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from middleware.auth_middleware import get_current_user, require_admin
import database as db

router = APIRouter(prefix="/admin", tags=["admin"])

BOT_API_URL   = os.getenv('BOT_API_URL', 'http://bot:8001')
BOT_API_TOKEN = os.getenv('BOT_API_TOKEN', '')


def _bot_headers():
    return {"Authorization": f"Bearer {BOT_API_TOKEN}"}


async def _bot(method: str, path: str, **kwargs):
    async with httpx.AsyncClient(timeout=10) as client:
        r = await getattr(client, method)(f"{BOT_API_URL}{path}",
                                          headers=_bot_headers(), **kwargs)
        if r.status_code >= 400:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        return r.json()


class ModerationAction(BaseModel):
    user_id:      int
    reason:       str = "Action depuis le panel"
    duration:     Optional[int] = None   # minutes (for timeout)


class CommandToggle(BaseModel):
    command_name: str
    enabled:      bool


# ── Commands ──────────────────────────────────────────────────────────────────

@router.get("/commands")
async def list_commands(user: dict = Depends(get_current_user)):
    require_admin(user)
    return await _bot('get', '/commands')


@router.post("/commands/toggle")
async def toggle_command(body: CommandToggle, user: dict = Depends(get_current_user)):
    require_admin(user)
    return await _bot('post', '/commands/toggle', json=body.model_dump())


# ── Moderation ────────────────────────────────────────────────────────────────

@router.post("/kick")
async def kick(body: ModerationAction, user: dict = Depends(get_current_user)):
    require_admin(user)
    return await _bot('post', '/moderation/kick', json={
        "user_id": body.user_id, "reason": body.reason, "moderator_id": int(user['sub'])
    })


@router.post("/ban")
async def ban(body: ModerationAction, user: dict = Depends(get_current_user)):
    require_admin(user)
    return await _bot('post', '/moderation/ban', json={
        "user_id": body.user_id, "reason": body.reason, "moderator_id": int(user['sub'])
    })


@router.post("/timeout")
async def timeout(body: ModerationAction, user: dict = Depends(get_current_user)):
    require_admin(user)
    return await _bot('post', '/moderation/timeout', json={
        "user_id": body.user_id, "reason": body.reason,
        "moderator_id": int(user['sub']),
        "duration_minutes": body.duration or 60,
    })


# ── Warns (direct DB) ─────────────────────────────────────────────────────────

@router.get("/warns/{user_id}")
async def get_warns(user_id: int, user: dict = Depends(get_current_user)):
    require_admin(user)
    warns = await db.fetch(
        "SELECT * FROM warn WHERE user_id = $1 ORDER BY create_time DESC", user_id
    )
    return {"warns": warns}


@router.post("/warns")
async def add_warn(body: ModerationAction, user: dict = Depends(get_current_user)):
    require_admin(user)
    return await _bot('post', '/warns', json={
        "user_id": body.user_id, "reason": body.reason, "moderator_id": int(user['sub'])
    })


@router.delete("/warns/{warn_id}")
async def delete_warn(warn_id: int, user: dict = Depends(get_current_user)):
    require_admin(user)
    await db.execute("DELETE FROM warn WHERE id = $1", warn_id)
    return {"success": True}


# ── Stats overview ────────────────────────────────────────────────────────────

@router.get("/stats")
async def server_stats(user: dict = Depends(get_current_user)):
    require_admin(user)
    members      = await db.fetchval("SELECT COUNT(*) FROM user_voice_data")
    total_msgs   = await db.fetchval("SELECT COALESCE(SUM(message_count), 0) FROM user_message_stats")
    total_warns  = await db.fetchval("SELECT COUNT(*) FROM warn")
    total_articles = await db.fetchval("SELECT COUNT(*) FROM articles WHERE published = TRUE")
    return {
        "members":        int(members or 0),
        "total_messages": int(total_msgs or 0),
        "total_warns":    int(total_warns or 0),
        "total_articles": int(total_articles or 0),
    }
