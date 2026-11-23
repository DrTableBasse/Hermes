"""Historique des tickets : global pour les admins, personnel pour chaque membre."""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from middleware.auth_middleware import get_current_user, require_permission
import database as db

# Origine opaque, aucun script, aucune ressource externe : seul le style en ligne du bot passe.
TRANSCRIPT_CSP = "sandbox; default-src 'none'; style-src 'unsafe-inline'"
TRANSCRIPT_HEADERS = {
    "Content-Security-Policy": TRANSCRIPT_CSP,
    "X-Content-Type-Options": "nosniff",
    "Cache-Control": "private, no-store",
}

router = APIRouter(prefix="/tickets", tags=["tickets"])

_STATUS = "^(all|open|closed)$"

_COLUMNS = """
    t.id,
    t.ticket_number,
    t.user_id,
    COALESCE(v.nickname, v.username, t.user_id::text) AS username,
    t.subject,
    t.status,
    t.created_at,
    t.closed_at,
    (t.transcript_html IS NOT NULL) AS has_transcript
"""


def _serialize(r) -> dict:
    return {
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


async def _list(status: str, page: int, limit: int, owner: int | None = None) -> dict:
    """Page de tickets ; `owner` restreint aux tickets de ce membre (paramètre lié, jamais interpolé)."""
    conditions: list[str] = []
    args: list = []
    if status != "all":
        conditions.append(f"t.status = ${len(args) + 1}")
        args.append(status)
    if owner is not None:
        conditions.append(f"t.user_id = ${len(args) + 1}")
        args.append(owner)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    rows = await db.fetch(
        f"""
        SELECT {_COLUMNS}
        FROM tickets t
        LEFT JOIN user_voice_data v ON v.user_id = t.user_id
        {where}
        ORDER BY t.created_at DESC
        LIMIT ${len(args) + 1} OFFSET ${len(args) + 2}
        """,
        *args, limit, (page - 1) * limit,
    )
    total = await db.fetchval(f"SELECT COUNT(*) FROM tickets t {where}", *args) or 0

    return {
        "tickets": [_serialize(r) for r in rows],
        "total": int(total),
        "page":  page,
        "limit": limit,
    }


@router.get("")
async def list_tickets(
    status: str = Query("all", pattern=_STATUS),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user: dict = Depends(get_current_user),
):
    require_permission(user, "tickets.manage")
    return await _list(status, page, limit)


@router.get("/mine")
async def my_tickets(
    status: str = Query("all", pattern=_STATUS),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user: dict = Depends(get_current_user),
):
    """Tickets ouverts par le membre connecté, mêmes champs que `GET /tickets`."""
    return await _list(status, page, limit, owner=int(user["sub"]))


@router.get("/{ticket_id}/transcript", response_class=HTMLResponse)
async def get_transcript(
    ticket_id: int,
    user: dict = Depends(get_current_user),
):
    row = await db.fetchrow(
        "SELECT user_id, transcript_html FROM tickets WHERE id = $1", ticket_id
    )
    # Droit « tickets.manage » : tout ticket. Membre : le sien seulement. Un ticket d'autrui
    # répond 403 (jamais 404 pour un autre membre qui le demande), pour ne pas révéler quels
    # identifiants existent.
    is_owner = row is not None and str(row["user_id"]) == str(user.get("sub"))
    if not is_owner:
        require_permission(user, "tickets.manage")
    if not row:
        raise HTTPException(status_code=404, detail="Ticket introuvable")
    if not row["transcript_html"]:
        raise HTTPException(status_code=404, detail="Aucun transcript pour ce ticket")

    # Servie sur l'origine du site (via le proxy) : isolée par une CSP « sandbox », qui couvre
    # aussi les transcriptions déjà en base, générées avant l'échappement complet du bot.
    return HTMLResponse(content=row["transcript_html"], headers=TRANSCRIPT_HEADERS)
