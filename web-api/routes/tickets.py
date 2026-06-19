# web-api/routes/tickets.py
"""Support ticket routes."""
import logging
import os
import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import database as db
from middleware.auth_middleware import get_current_user, require_admin

router = APIRouter(prefix="/tickets", tags=["tickets"])
logger = logging.getLogger(__name__)

BOT_API_URL   = os.getenv("BOT_API_URL", "http://bot:8001")
BOT_API_TOKEN = os.getenv("BOT_API_TOKEN", "")


def _bot_headers():
    return {"Authorization": f"Bearer {BOT_API_TOKEN}"}


async def _bot(method: str, path: str, **kwargs):
    async with httpx.AsyncClient(timeout=10) as client:
        r = await getattr(client, method)(
            f"{BOT_API_URL}{path}", headers=_bot_headers(), **kwargs
        )
        if r.status_code >= 400:
            try:
                detail = r.json().get("detail", r.text)
            except Exception:
                detail = r.text
            raise HTTPException(status_code=r.status_code, detail=detail)
        return r.json()


class TicketCreate(BaseModel):
    title: str


class TicketAdminCreate(BaseModel):
    user_id: str
    title: str


class MessageCreate(BaseModel):
    content: str


def _serialize_ticket(t) -> dict:
    return {
        "id":                 t["id"],
        "user_id":            str(t["user_id"]),
        "title":              t["title"],
        "status":             t["status"],
        "discord_channel_id": str(t["discord_channel_id"]) if t["discord_channel_id"] else None,
        "created_at":         t["created_at"].isoformat() if t["created_at"] else None,
        "closed_at":          t["closed_at"].isoformat() if t["closed_at"] else None,
        "created_by_admin":   t["created_by_admin"],
        "username":           t.get("username"),
        "discord_avatar":     t.get("discord_avatar"),
    }


def _serialize_message(m) -> dict:
    return {
        "id":          m["id"],
        "ticket_id":   m["ticket_id"],
        "author_id":   str(m["author_id"]),
        "author_name": m["author_name"],
        "content":     m["content"],
        "source":      m["source"],
        "created_at":  m["created_at"].isoformat() if m["created_at"] else None,
    }


async def _get_username(user_id: int) -> str:
    row = await db.fetchrow(
        "SELECT COALESCE(nickname, username) AS name FROM user_voice_data WHERE user_id = $1",
        user_id,
    )
    return row["name"] if row else str(user_id)


@router.post("", status_code=201)
async def create_ticket(body: TicketCreate, user: dict = Depends(get_current_user)):
    user_id = int(user["sub"])
    existing = await db.fetchval(
        "SELECT id FROM tickets WHERE user_id = $1 AND status = 'open'", user_id
    )
    if existing:
        raise HTTPException(status_code=409, detail="Tu as déjà un ticket ouvert.")
    username = await _get_username(user_id)
    ticket_id = await db.fetchval(
        "INSERT INTO tickets (user_id, title) VALUES ($1, $2) RETURNING id",
        user_id,
        body.title,
    )
    try:
        result = await _bot("post", "/tickets/create", json={
            "user_id": user_id, "username": username,
            "ticket_id": ticket_id, "title": body.title,
        })
        channel_id = result.get("discord_channel_id")
        if channel_id:
            await db.execute(
                "UPDATE tickets SET discord_channel_id = $1 WHERE id = $2",
                int(channel_id), ticket_id,
            )
    except Exception as e:
        logger.warning("Ticket #%s: création salon Discord échouée: %s", ticket_id, e)
    ticket = await db.fetchrow("SELECT * FROM tickets WHERE id = $1", ticket_id)
    return _serialize_ticket(ticket)


@router.post("/admin", status_code=201)
async def create_ticket_admin(body: TicketAdminCreate, user: dict = Depends(get_current_user)):
    require_admin(user)
    target_id = int(body.user_id)
    existing = await db.fetchval(
        "SELECT id FROM tickets WHERE user_id = $1 AND status = 'open'", target_id
    )
    if existing:
        raise HTTPException(status_code=409, detail="Cet utilisateur a déjà un ticket ouvert.")
    username = await _get_username(target_id)
    ticket_id = await db.fetchval(
        "INSERT INTO tickets (user_id, title, created_by_admin) VALUES ($1, $2, TRUE) RETURNING id",
        target_id, body.title,
    )
    try:
        result = await _bot("post", "/tickets/create", json={
            "user_id": target_id, "username": username,
            "ticket_id": ticket_id, "title": body.title,
        })
        channel_id = result.get("discord_channel_id")
        if channel_id:
            await db.execute(
                "UPDATE tickets SET discord_channel_id = $1 WHERE id = $2",
                int(channel_id), ticket_id,
            )
    except Exception as e:
        logger.warning("Ticket #%s: création salon Discord échouée: %s", ticket_id, e)
    ticket = await db.fetchrow("SELECT * FROM tickets WHERE id = $1", ticket_id)
    return _serialize_ticket(ticket)


@router.get("")
async def list_tickets(user: dict = Depends(get_current_user)):
    user_id = int(user["sub"])
    if user.get("is_admin"):
        rows = await db.fetch(
            """SELECT t.*, v.username, v.discord_avatar
               FROM tickets t
               LEFT JOIN user_voice_data v ON t.user_id = v.user_id
               ORDER BY
                 CASE t.status WHEN 'open' THEN 0 WHEN 'resolved' THEN 1 ELSE 2 END,
                 t.created_at DESC"""
        )
    else:
        rows = await db.fetch(
            "SELECT * FROM tickets WHERE user_id = $1 ORDER BY created_at DESC",
            user_id,
        )
    return {"tickets": [_serialize_ticket(r) for r in rows]}


@router.get("/{ticket_id}")
async def get_ticket(ticket_id: int, user: dict = Depends(get_current_user)):
    user_id = int(user["sub"])
    ticket = await db.fetchrow("SELECT * FROM tickets WHERE id = $1", ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket introuvable")
    if not user.get("is_admin") and ticket["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Accès refusé")
    messages = await db.fetch(
        "SELECT * FROM ticket_messages WHERE ticket_id = $1 ORDER BY created_at ASC",
        ticket_id,
    )
    return {
        **_serialize_ticket(ticket),
        "messages": [_serialize_message(m) for m in messages],
    }


@router.post("/{ticket_id}/message")
async def send_message(
    ticket_id: int, body: MessageCreate, user: dict = Depends(get_current_user)
):
    user_id = int(user["sub"])
    ticket = await db.fetchrow("SELECT * FROM tickets WHERE id = $1", ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket introuvable")
    if not user.get("is_admin") and ticket["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Accès refusé")
    if ticket["status"] != "open":
        raise HTTPException(status_code=409, detail="Ce ticket est fermé.")
    author_name = await _get_username(user_id)
    await db.execute(
        """INSERT INTO ticket_messages
               (ticket_id, author_id, author_name, content, source)
           VALUES ($1, $2, $3, $4, 'web')""",
        ticket_id, user_id, author_name, body.content,
    )
    try:
        await _bot("post", f"/tickets/{ticket_id}/message", json={
            "content": body.content, "author_name": author_name,
        })
    except Exception as e:
        logger.warning("Ticket #%s: relay Discord échoué: %s", ticket_id, e)
    return {"success": True}


@router.post("/{ticket_id}/resolve")
async def resolve_ticket(ticket_id: int, user: dict = Depends(get_current_user)):
    user_id = int(user["sub"])
    ticket = await db.fetchrow("SELECT * FROM tickets WHERE id = $1", ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket introuvable")
    if ticket["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Accès refusé")
    if ticket["status"] != "open":
        raise HTTPException(status_code=409, detail="Ce ticket n'est pas ouvert.")
    await db.execute(
        "UPDATE tickets SET status = 'resolved', closed_at = NOW() WHERE id = $1",
        ticket_id,
    )
    return {"success": True}


@router.post("/{ticket_id}/close")
async def close_ticket(ticket_id: int, user: dict = Depends(get_current_user)):
    require_admin(user)
    ticket = await db.fetchrow("SELECT * FROM tickets WHERE id = $1", ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket introuvable")
    if ticket["status"] == "closed":
        raise HTTPException(status_code=409, detail="Ticket déjà fermé.")
    await db.execute(
        "UPDATE tickets SET status = 'closed', closed_at = NOW() WHERE id = $1",
        ticket_id,
    )
    try:
        await _bot("post", f"/tickets/{ticket_id}/close", json={})
    except Exception as e:
        logger.warning("Ticket #%s: fermeture Discord échouée: %s", ticket_id, e)
    return {"success": True}
