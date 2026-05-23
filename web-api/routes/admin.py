"""Admin routes — proxy to the bot's internal API."""
import json
import logging
import os
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from middleware.auth_middleware import get_current_user, require_admin
import database as db

router = APIRouter(prefix="/admin", tags=["admin"])
logger = logging.getLogger(__name__)

BOT_API_URL   = os.getenv('BOT_API_URL', 'http://bot:8001')
BOT_API_TOKEN = os.getenv('BOT_API_TOKEN', '')


def _bot_headers():
    return {"Authorization": f"Bearer {BOT_API_TOKEN}"}


async def _bot(method: str, path: str, **kwargs):
    async with httpx.AsyncClient(timeout=10) as client:
        r = await getattr(client, method)(f"{BOT_API_URL}{path}",
                                          headers=_bot_headers(), **kwargs)
        if r.status_code >= 400:
            try:
                detail = r.json().get("detail", r.text)
            except Exception:
                detail = r.text
            raise HTTPException(status_code=r.status_code, detail=detail)
        return r.json()


async def _log(action_type: str, actor_id: int,
               target_id: int | None = None,
               details: dict | None = None):
    """Insert into admin_logs. Never raises."""
    try:
        actor = await db.fetchrow(
            "SELECT COALESCE(nickname, username) AS name FROM user_voice_data WHERE user_id = $1",
            actor_id,
        )
        actor_name = actor["name"] if actor else str(actor_id)

        target_name = None
        if target_id:
            target = await db.fetchrow(
                "SELECT COALESCE(nickname, username) AS name FROM user_voice_data WHERE user_id = $1",
                target_id,
            )
            target_name = target["name"] if target else str(target_id)

        await db.execute(
            """INSERT INTO admin_logs
                   (action_type, actor_id, actor_name, target_id, target_name, details)
               VALUES ($1, $2, $3, $4, $5, $6::jsonb)""",
            action_type, actor_id, actor_name, target_id, target_name,
            json.dumps(details or {}),
        )
    except Exception as e:
        logger.warning(f"admin_logs insert failed: {e}")


class ModerationAction(BaseModel):
    user_id:  str
    reason:   str = "Action depuis le panel"
    duration: Optional[int] = None

    @property
    def user_id_int(self) -> int:
        return int(self.user_id)


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
    try:
        moderator_id = int(user['sub'])
    except (KeyError, ValueError, TypeError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid moderator_id in token: {e}")
    guild_id_str = os.getenv('GUILD_ID', '')
    result = await _bot('post', '/commands/toggle', json={
        **body.model_dump(),
        "moderator_id": moderator_id,
        "guild_id": int(guild_id_str) if guild_id_str else None,
    })
    await _log('command_toggle', moderator_id, details={
        "command_name": body.command_name,
        "enabled":      body.enabled,
    })
    return result


# ── Moderation ────────────────────────────────────────────────────────────────

@router.post("/kick")
async def kick(body: ModerationAction, user: dict = Depends(get_current_user)):
    require_admin(user)
    result = await _bot('post', '/moderation/kick', json={
        "user_id": body.user_id_int, "reason": body.reason, "moderator_id": int(user['sub'])
    })
    await _log('kick', int(user['sub']), body.user_id_int, {"reason": body.reason})
    return result


@router.post("/ban")
async def ban(body: ModerationAction, user: dict = Depends(get_current_user)):
    require_admin(user)
    result = await _bot('post', '/moderation/ban', json={
        "user_id": body.user_id_int, "reason": body.reason, "moderator_id": int(user['sub'])
    })
    await _log('ban', int(user['sub']), body.user_id_int, {"reason": body.reason})
    return result


@router.post("/timeout")
async def timeout(body: ModerationAction, user: dict = Depends(get_current_user)):
    require_admin(user)
    duration = body.duration or 60
    result = await _bot('post', '/moderation/timeout', json={
        "user_id": body.user_id_int, "reason": body.reason,
        "moderator_id": int(user['sub']),
        "duration_minutes": duration,
    })
    await _log('timeout', int(user['sub']), body.user_id_int, {
        "reason": body.reason, "duration_minutes": duration
    })
    return result


# ── Warns ─────────────────────────────────────────────────────────────────────

@router.get("/warns")
async def get_all_warns(user: dict = Depends(get_current_user)):
    require_admin(user)
    warns = await db.fetch("""
        SELECT w.id, w.user_id, w.reason, w.create_time, w.moderator_id,
               u.username, u.nickname, u.discord_avatar,
               m.username AS moderator_username
        FROM warn w
        JOIN user_voice_data u ON w.user_id = u.user_id
        LEFT JOIN user_voice_data m ON w.moderator_id = m.user_id
        ORDER BY w.create_time DESC
        LIMIT 300
    """)
    return {"warns": [
        {
            "id":                 w["id"],
            "user_id":            str(w["user_id"]),
            "username":           w["nickname"] or w["username"],
            "discord_avatar":     w["discord_avatar"],
            "reason":             w["reason"],
            "create_time":        w["create_time"],
            "moderator_id":       str(w["moderator_id"]),
            "moderator_username": w["moderator_username"],
        }
        for w in warns
    ]}


@router.get("/warns/{user_id}")
async def get_warns(user_id: str, user: dict = Depends(get_current_user)):
    require_admin(user)
    warns = await db.fetch("""
        SELECT w.*, v.username AS moderator_username
        FROM warn w
        LEFT JOIN user_voice_data v ON w.moderator_id = v.user_id
        WHERE w.user_id = $1
        ORDER BY w.create_time DESC
    """, int(user_id))
    return {"warns": [
        dict(w) | {
            "user_id":            str(w["user_id"]),
            "moderator_id":       str(w["moderator_id"]),
            "moderator_username": w["moderator_username"],
        }
        for w in warns
    ]}


@router.post("/warns")
async def add_warn(body: ModerationAction, user: dict = Depends(get_current_user)):
    require_admin(user)
    result = await _bot('post', '/warns', json={
        "user_id": body.user_id_int, "reason": body.reason, "moderator_id": int(user['sub'])
    })
    await _log('warn', int(user['sub']), body.user_id_int, {"reason": body.reason})
    return result


@router.delete("/warns/{warn_id}")
async def delete_warn(warn_id: int, user: dict = Depends(get_current_user)):
    require_admin(user)
    warn = await db.fetchrow("SELECT user_id, reason FROM warn WHERE id = $1", warn_id)
    await db.execute("DELETE FROM warn WHERE id = $1", warn_id)
    if warn:
        await _log('delete_warn', int(user['sub']), warn['user_id'], {
            "warn_id": warn_id, "reason": warn['reason']
        })
    return {"success": True}


# ── Admin logs ────────────────────────────────────────────────────────────────

@router.get("/logs")
async def get_admin_logs(
    user: dict = Depends(get_current_user),
    action_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
):
    require_admin(user)
    limit  = 50
    offset = (page - 1) * limit

    if action_type:
        types = action_type.split(',')
        rows = await db.fetch(
            """SELECT * FROM admin_logs
               WHERE action_type = ANY($1::varchar[])
               ORDER BY created_at DESC LIMIT $2 OFFSET $3""",
            types, limit, offset,
        )
        total = await db.fetchval(
            "SELECT COUNT(*) FROM admin_logs WHERE action_type = ANY($1::varchar[])", types
        )
    else:
        rows = await db.fetch(
            "SELECT * FROM admin_logs ORDER BY created_at DESC LIMIT $1 OFFSET $2",
            limit, offset,
        )
        total = await db.fetchval("SELECT COUNT(*) FROM admin_logs")

    total = int(total or 0)
    return {
        "logs": [
            {
                "id":          r["id"],
                "action_type": r["action_type"],
                "actor_id":    str(r["actor_id"]) if r["actor_id"] else None,
                "actor_name":  r["actor_name"],
                "target_id":   str(r["target_id"]) if r["target_id"] else None,
                "target_name": r["target_name"],
                "details":     r["details"] or {},
                "created_at":  r["created_at"].isoformat(),
            }
            for r in rows
        ],
        "total": total,
        "page":  page,
        "pages": max(1, -(-total // limit)),
    }


# ── User search ───────────────────────────────────────────────────────────────

@router.get("/users/search")
async def search_users(q: str, user: dict = Depends(get_current_user)):
    require_admin(user)
    if len(q) < 2:
        return {"users": []}
    rows = await db.fetch(
        """SELECT user_id, username, discord_avatar
           FROM user_voice_data
           WHERE username ILIKE $1
           ORDER BY username LIMIT 10""",
        f"%{q}%",
    )
    return {"users": [
        {"user_id": str(r["user_id"]), "username": r["username"], "discord_avatar": r["discord_avatar"]}
        for r in rows
    ]}


# ── Stats overview ────────────────────────────────────────────────────────────

@router.get("/stats")
async def server_stats(user: dict = Depends(get_current_user)):
    require_admin(user)
    members        = await db.fetchval("SELECT COUNT(*) FROM user_voice_data WHERE is_member = TRUE")
    total_msgs     = await db.fetchval("SELECT COALESCE(SUM(message_count), 0) FROM user_message_stats")
    total_warns    = await db.fetchval("SELECT COUNT(*) FROM warn")
    total_articles = await db.fetchval("SELECT COUNT(*) FROM articles WHERE published = TRUE")
    return {
        "members":        int(members or 0),
        "total_messages": int(total_msgs or 0),
        "total_warns":    int(total_warns or 0),
        "total_articles": int(total_articles or 0),
    }


# ── Quest templates ───────────────────────────────────────────────────────────

QUEST_TYPES = ('messages', 'voice_minutes', 'bumps', 'invites', 'images_posted', 'reactions_given')


class QuestTemplateBody(BaseModel):
    title:        str
    description:  Optional[str] = None
    quest_type:   str
    target_value: int
    xp_reward:    int = 50
    icon:         str = '📋'
    is_enabled:   bool = True

    def validate_quest_type(self):
        if self.quest_type not in QUEST_TYPES:
            raise HTTPException(status_code=400, detail=f"quest_type must be one of: {', '.join(QUEST_TYPES)}")


class DeployQuestsBody(BaseModel):
    count: int = 8


@router.get("/quest-templates")
async def list_quest_templates(user: dict = Depends(get_current_user)):
    require_admin(user)
    rows = await db.fetch("SELECT * FROM quest_templates ORDER BY quest_type, target_value")
    return {"templates": [dict(r) for r in rows]}


@router.post("/quest-templates", status_code=201)
async def create_quest_template(body: QuestTemplateBody, user: dict = Depends(get_current_user)):
    require_admin(user)
    body.validate_quest_type()
    row = await db.fetchrow("""
        INSERT INTO quest_templates (title, description, quest_type, target_value, xp_reward, icon, is_enabled)
        VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING *
    """, body.title, body.description, body.quest_type, body.target_value,
        body.xp_reward, body.icon, body.is_enabled)
    await _log('quest_template_create', int(user['sub']), details={"title": body.title})
    return dict(row)


@router.put("/quest-templates/{template_id}")
async def update_quest_template(
    template_id: int, body: QuestTemplateBody, user: dict = Depends(get_current_user)
):
    require_admin(user)
    body.validate_quest_type()
    row = await db.fetchrow("""
        UPDATE quest_templates
        SET title=$1, description=$2, quest_type=$3, target_value=$4, xp_reward=$5, icon=$6, is_enabled=$7
        WHERE id=$8 RETURNING *
    """, body.title, body.description, body.quest_type, body.target_value,
        body.xp_reward, body.icon, body.is_enabled, template_id)
    if not row:
        raise HTTPException(status_code=404, detail="Template introuvable")
    await _log('quest_template_update', int(user['sub']), details={"id": template_id, "title": body.title})
    return dict(row)


@router.delete("/quest-templates/{template_id}", status_code=204)
async def delete_quest_template(template_id: int, user: dict = Depends(get_current_user)):
    require_admin(user)
    await db.execute("DELETE FROM quest_templates WHERE id = $1", template_id)
    await _log('quest_template_delete', int(user['sub']), details={"id": template_id})


@router.get("/quests/active")
async def get_active_quests(user: dict = Depends(get_current_user)):
    require_admin(user)
    from datetime import date
    today = date.today()
    rows = await db.fetch("""
        SELECT q.*,
               COUNT(uqp.user_id)                                  AS participant_count,
               COUNT(uqp.user_id) FILTER (WHERE uqp.completed)    AS completed_count
        FROM weekly_quests q
        LEFT JOIN user_quest_progress uqp ON q.id = uqp.quest_id
        WHERE q.is_active = TRUE AND q.week_end >= $1
        GROUP BY q.id
        ORDER BY q.created_at DESC
    """, today)
    return {"quests": [dict(r) for r in rows]}


@router.post("/quests/deploy")
async def deploy_weekly_quests(body: DeployQuestsBody, user: dict = Depends(get_current_user)):
    require_admin(user)
    from datetime import date, timedelta
    today      = date.today()
    week_start = today - timedelta(days=today.weekday())
    week_end   = week_start + timedelta(days=6)

    templates = await db.fetch(
        "SELECT * FROM quest_templates WHERE is_enabled = TRUE ORDER BY RANDOM() LIMIT $1",
        min(max(body.count, 1), 20),
    )
    if not templates:
        raise HTTPException(status_code=400, detail="Aucun template de quête activé")

    deployed = 0
    for t in templates:
        await db.execute("""
            INSERT INTO weekly_quests (title, description, quest_type, target_value, xp_reward, icon, week_start, week_end)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """, t['title'], t['description'], t['quest_type'], t['target_value'],
            t['xp_reward'], t['icon'], week_start, week_end)
        deployed += 1

    await _log('quest_deploy', int(user['sub']), details={"count": deployed, "week_start": str(week_start)})
    return {"deployed": deployed, "week_start": str(week_start), "week_end": str(week_end)}
