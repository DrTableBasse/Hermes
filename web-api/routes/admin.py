"""Admin routes — proxy to the bot's internal API."""
import asyncio
import json
import logging
import os
from typing import Optional

import httpx
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from middleware.auth_middleware import get_current_user, require_permission
import database as db
from media_files import invalidate_hidden_gallery
from routes import gallery

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


KIND_OF_ACTION: dict[str, str] = {
    "kick": "sanction",
    "ban": "sanction",
    "timeout": "sanction",
    "warn": "sanction",
    "delete_warn": "sanction",
    "command_toggle": "setting",
    "quest_template_create": "content",
    "quest_template_update": "content",
    "quest_template_delete": "content",
    "quest_deploy": "content",
}


async def _log(action_type: str, actor_id: int,
               target_id: int | None = None,
               details: dict | None = None,
               success: bool = True):
    """Insert into audit_events (source 'site'). Never raises."""
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
            """INSERT INTO audit_events
                   (kind, action, source, actor_id, actor_name,
                    target_id, target_name, details, success)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9)""",
            KIND_OF_ACTION.get(action_type, "setting"), action_type, "site",
            actor_id, actor_name, target_id, target_name,
            json.dumps(details or {}), success,
        )
    except Exception as e:
        logger.warning(f"audit_events insert failed: {e}")


async def _sanction(action_type: str, path: str, payload: dict,
                    actor_id: int, target_id: int, details: dict):
    """Call the bot for a sanction and journal it, success or failure.

    On failure, writes a ``success=false`` row with ``details.error`` then re-raises.
    """
    try:
        result = await _bot('post', path, json=payload)
    except Exception as e:
        error = e.detail if isinstance(e, HTTPException) else str(e)
        await _log(action_type, actor_id, target_id,
                   {**details, "error": str(error)}, success=False)
        raise
    await _log(action_type, actor_id, target_id, details)
    return result


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
    require_permission(user, "settings.manage")
    return await _bot('get', '/commands')


@router.post("/commands/toggle")
async def toggle_command(body: CommandToggle, user: dict = Depends(get_current_user)):
    require_permission(user, "settings.manage")
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
    require_permission(user, "moderation.act")
    return await _sanction('kick', '/moderation/kick', {
        "user_id": body.user_id_int, "reason": body.reason, "moderator_id": int(user['sub'])
    }, int(user['sub']), body.user_id_int, {"reason": body.reason})


@router.post("/ban")
async def ban(body: ModerationAction, user: dict = Depends(get_current_user)):
    require_permission(user, "moderation.act")
    return await _sanction('ban', '/moderation/ban', {
        "user_id": body.user_id_int, "reason": body.reason, "moderator_id": int(user['sub'])
    }, int(user['sub']), body.user_id_int, {"reason": body.reason})


@router.post("/timeout")
async def timeout(body: ModerationAction, user: dict = Depends(get_current_user)):
    require_permission(user, "moderation.act")
    duration = body.duration or 60
    return await _sanction('timeout', '/moderation/timeout', {
        "user_id": body.user_id_int, "reason": body.reason,
        "moderator_id": int(user['sub']),
        "duration_minutes": duration,
    }, int(user['sub']), body.user_id_int, {
        "reason": body.reason, "duration_minutes": duration
    })


# ── Warns ─────────────────────────────────────────────────────────────────────

@router.get("/warns")
async def get_all_warns(user: dict = Depends(get_current_user)):
    require_permission(user, "moderation.view")
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
    require_permission(user, "moderation.view")
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
    require_permission(user, "moderation.act")
    return await _sanction('warn', '/warns', {
        "user_id": body.user_id_int, "reason": body.reason, "moderator_id": int(user['sub'])
    }, int(user['sub']), body.user_id_int, {"reason": body.reason})


@router.delete("/warns/{warn_id}")
async def delete_warn(warn_id: int, user: dict = Depends(get_current_user)):
    require_permission(user, "moderation.act")
    warn = await db.fetchrow("SELECT user_id, reason FROM warn WHERE id = $1", warn_id)
    await db.execute("DELETE FROM warn WHERE id = $1", warn_id)
    if warn:
        await _log('delete_warn', int(user['sub']), warn['user_id'], {
            "warn_id": warn_id, "reason": warn['reason']
        })
    return {"success": True}


# ── User search ───────────────────────────────────────────────────────────────

@router.get("/users/search")
async def search_users(q: str, user: dict = Depends(get_current_user)):
    require_permission(user, "moderation.view")
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
    require_permission(user, "admin.view")
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
    require_permission(user, "quests.manage")
    rows = await db.fetch("SELECT * FROM quest_templates ORDER BY quest_type, target_value")
    return {"templates": [dict(r) for r in rows]}


@router.post("/quest-templates", status_code=201)
async def create_quest_template(body: QuestTemplateBody, user: dict = Depends(get_current_user)):
    require_permission(user, "quests.manage")
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
    require_permission(user, "quests.manage")
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
    require_permission(user, "quests.manage")
    await db.execute("DELETE FROM quest_templates WHERE id = $1", template_id)
    await _log('quest_template_delete', int(user['sub']), details={"id": template_id})


@router.get("/quests/active")
async def get_active_quests(user: dict = Depends(get_current_user)):
    require_permission(user, "quests.manage")
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
    require_permission(user, "quests.manage")
    from datetime import date, timedelta
    today      = date.today()
    week_start = today - timedelta(days=today.weekday())
    week_end   = week_start + timedelta(days=6)

    # At most 2 per quest_type to ensure category diversity
    templates = await db.fetch("""
        SELECT * FROM (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY quest_type ORDER BY RANDOM()) AS rn
            FROM quest_templates WHERE is_enabled = TRUE
        ) t WHERE rn <= 2
        ORDER BY RANDOM()
        LIMIT $1
    """, min(max(body.count, 1), 20))
    if not templates:
        raise HTTPException(status_code=400, detail="Aucun template de quête activé")

    # Deactivate all current active quests before deploying new ones
    await db.execute("UPDATE weekly_quests SET is_active = FALSE WHERE is_active = TRUE")

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


# ── Analytics dashboard ───────────────────────────────────────────────────────

@router.get("/analytics")
async def get_analytics(user: dict = Depends(get_current_user)):
    require_permission(user, "analytics.view")
    from datetime import datetime, timedelta, timezone
    from collections import defaultdict

    # Admin actions last 14 days, grouped by day + action type
    action_rows = await db.fetch("""
        SELECT
            DATE(occurred_at AT TIME ZONE 'UTC') AS day,
            action AS action_type,
            COUNT(*) AS cnt
        FROM audit_events
        WHERE occurred_at >= NOW() - INTERVAL '14 days'
          AND kind = 'sanction'
          AND action IN ('warn', 'kick', 'ban', 'timeout')
        GROUP BY 1, 2
        ORDER BY 1
    """)

    today = datetime.now(timezone.utc).date()
    days = [(today - timedelta(days=i)).isoformat() for i in range(13, -1, -1)]
    by_day: dict = defaultdict(lambda: {"warn": 0, "kick": 0, "ban": 0, "timeout": 0})
    for r in action_rows:
        d = r["day"].isoformat() if hasattr(r["day"], "isoformat") else str(r["day"])
        by_day[d][r["action_type"]] = int(r["cnt"])
    actions_14d = [{"date": d, "label": d[5:], **by_day[d]} for d in days]

    # Level distribution
    level_dist = await db.fetch("""
        SELECT
            CASE
                WHEN current_level BETWEEN 1 AND 5   THEN '1-5'
                WHEN current_level BETWEEN 6 AND 10  THEN '6-10'
                WHEN current_level BETWEEN 11 AND 20 THEN '11-20'
                WHEN current_level BETWEEN 21 AND 50 THEN '21-50'
                ELSE '50+'
            END AS level_range,
            COUNT(*) AS count,
            MIN(current_level) AS sort_key
        FROM user_xp
        GROUP BY 1
        ORDER BY 3
    """)

    # Quest completion for current active week
    quest_rows = await db.fetch("""
        SELECT
            q.title, q.icon,
            COUNT(uqp.user_id)                                 AS participants,
            COUNT(uqp.user_id) FILTER (WHERE uqp.completed)   AS completed
        FROM weekly_quests q
        LEFT JOIN user_quest_progress uqp ON q.id = uqp.quest_id
        WHERE q.is_active = TRUE
        GROUP BY q.id, q.title, q.icon
        ORDER BY q.id
    """)

    # Top 5 by XP this week
    top_xp = await db.fetch("""
        SELECT COALESCE(u.nickname, u.username) AS username, x.weekly_xp
        FROM user_xp x
        JOIN user_voice_data u ON x.user_id = u.user_id
        WHERE u.is_member = TRUE AND x.weekly_xp > 0
        ORDER BY x.weekly_xp DESC
        LIMIT 5
    """)

    # Summary KPIs
    active_members    = await db.fetchval("SELECT COUNT(*) FROM user_voice_data WHERE is_member = TRUE")
    total_messages    = await db.fetchval("SELECT COALESCE(SUM(message_count), 0) FROM user_message_stats")
    warns_30d         = await db.fetchval(
        "SELECT COUNT(*) FROM warn WHERE create_time >= $1",
        int((datetime.now(timezone.utc) - timedelta(days=30)).timestamp())
    )
    quests_done_7d    = await db.fetchval(
        """SELECT COUNT(*) FROM user_quest_progress uqp
           JOIN weekly_quests q ON q.id = uqp.quest_id
           WHERE uqp.completed = TRUE
             AND q.week_start >= CURRENT_DATE - INTERVAL '7 days'"""
    )

    return {
        "actions_14d": actions_14d,
        "level_distribution": [
            {"level_range": r["level_range"], "count": int(r["count"])}
            for r in level_dist
        ],
        "quest_completion": [
            {
                "title":        f"{r['icon']} {r['title']}",
                "participants": int(r["participants"]),
                "completed":    int(r["completed"]),
                "rate":         round(int(r["completed"]) / int(r["participants"]) * 100, 1) if int(r["participants"]) > 0 else 0,
            }
            for r in quest_rows
        ],
        "top_xp_weekly": [
            {"username": r["username"], "weekly_xp": int(r["weekly_xp"])}
            for r in top_xp
        ],
        "summary": {
            "active_members":   int(active_members or 0),
            "total_messages":   int(total_messages or 0),
            "warns_30d":        int(warns_30d or 0),
            "quests_done_7d":   int(quests_done_7d or 0),
        },
    }


# ── Galerie ──────────────────────────────────────────────────────────────────

class GalleryVisibility(BaseModel):
    hidden: bool


@router.get("/gallery")
async def list_gallery_admin(user: dict = Depends(get_current_user),
                             limit: int = Query(100, ge=1, le=200)):
    """Galerie complète pour la modération : éléments masqués compris, avec leur état."""
    require_permission(user, "gallery.manage")
    rows = await db.fetch(
        """SELECT g.id, g.kind, g.file_name, g.clip_url, g.clip_provider, g.caption, g.hidden,
                  g.author_id, g.created_at, v.username, v.discord_avatar
           FROM gallery_items g
           LEFT JOIN user_voice_data v ON v.user_id = g.author_id
           ORDER BY g.created_at DESC
           LIMIT $1""", limit)
    return {"items": [{**gallery._item(r), "hidden": bool(r["hidden"])} for r in rows]}


@router.patch("/gallery/{item_id}")
async def set_gallery_hidden(item_id: int, body: GalleryVisibility,
                             user: dict = Depends(get_current_user)):
    require_permission(user, "gallery.manage")
    row = await db.fetchrow(
        "UPDATE gallery_items SET hidden = $1 WHERE id = $2 RETURNING id", body.hidden, item_id)
    if not row:
        raise HTTPException(status_code=404, detail="Élément introuvable")
    invalidate_hidden_gallery()
    return {"id": item_id, "hidden": body.hidden}


@router.delete("/gallery/{item_id}", status_code=204)
async def delete_gallery_item(item_id: int, user: dict = Depends(get_current_user)):
    require_permission(user, "gallery.manage")
    row = await db.fetchrow(
        "DELETE FROM gallery_items WHERE id = $1 RETURNING file_name", item_id)
    if not row:
        raise HTTPException(status_code=404, detail="Élément introuvable")
    invalidate_hidden_gallery()
    if row["file_name"]:
        try:
            # .name : le nom vient de la base, jamais un chemin hors du dossier.
            await asyncio.to_thread(
                (gallery.GALLERY_DIR / Path(row["file_name"]).name).unlink, missing_ok=True)
        except OSError as exc:
            logger.warning("Fichier de galerie non supprimé (%s) : %s", row["file_name"], exc)
    return Response(status_code=204)
