"""Ticket history — admin only."""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from middleware.auth_middleware import get_current_user, require_admin
import database as db

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.get("")
async def list_tickets(
    status: str = Query("all", pattern="^(all|open|closed)$"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user: dict = Depends(get_current_user),
):
    require_admin(user)

    offset = (page - 1) * limit
    where = "" if status == "all" else f"WHERE t.status = '{status}'"

    rows = await db.fetch(f"""
        SELECT
            t.id,
            t.ticket_number,
            t.user_id,
            COALESCE(v.nickname, v.username, t.user_id::text) AS username,
            t.subject,
            t.status,
            t.created_at,
            t.closed_at,
            (t.transcript_html IS NOT NULL) AS has_transcript
        FROM tickets t
        LEFT JOIN user_voice_data v ON v.user_id = t.user_id
        {where}
        ORDER BY t.created_at DESC
        LIMIT $1 OFFSET $2
    """, limit, offset)

    total = await db.fetchval(
        f"SELECT COUNT(*) FROM tickets t {where}"
    ) or 0

    return {
        "tickets": [
            {
                "id":            r["id"],
                "ticket_number": r["ticket_number"],
                "user_id":       str(r["user_id"]),
                "username":      r["username"],
                "subject":       r["subject"],
                "status":        r["status"],
                "created_at":    r["created_at"].isoformat() if r["created_at"] else None,
                "closed_at":     r["closed_at"].isoformat() if r["closed_at"] else None,
                "has_transcript": r["has_transcript"],
            }
            for r in rows
        ],
        "total": int(total),
        "page":  page,
        "limit": limit,
    }


@router.get("/{ticket_id}/transcript", response_class=HTMLResponse)
async def get_transcript(
    ticket_id: int,
    user: dict = Depends(get_current_user),
):
    require_admin(user)

    row = await db.fetchrow(
        "SELECT transcript_html FROM tickets WHERE id = $1", ticket_id
    )
    if not row:
        raise HTTPException(status_code=404, detail="Ticket introuvable")
    if not row["transcript_html"]:
        raise HTTPException(status_code=404, detail="Aucun transcript pour ce ticket")

    return HTMLResponse(content=row["transcript_html"])
