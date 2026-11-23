"""Lecture du journal unique (``audit_events``) : liste filtrée, facettes et export CSV.

Réservé aux admins. Toutes les valeurs fournies par l'utilisateur passent en
paramètres de requête (jamais dans le SQL) ; ``kind`` et ``source`` sont validés
contre des listes fermées, les dates invalides renvoient 422.
"""
import csv
import io
import json
import time
from datetime import datetime, timedelta
from typing import Any, Mapping, Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

import database as db
from middleware.auth_middleware import get_current_user, require_admin

router = APIRouter(prefix="/admin", tags=["audit"])

PAGE_SIZE = 50
CSV_MAX_ROWS = 10_000
FACETS_TTL_S = 60
PARIS = ZoneInfo("Europe/Paris")
MAX_BIGINT = 2**63 - 1

KINDS = frozenset({
    "command", "sanction", "message", "voice", "member", "member_role", "role", "channel",
    "thread", "invite", "emoji", "server", "permission", "setting", "game", "site_access", "content",
})
SOURCES = frozenset({"site", "hermes", "discord"})

CSV_HEADER = ["Date", "Type", "Action", "Source", "Auteur", "Cible", "Salon", "Succès", "Détails"]
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")

_facets_cache: dict = {"at": 0.0, "value": None}


def _unprocessable(message: str) -> HTTPException:
    return HTTPException(status_code=422, detail=message)


def _split(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def _closed_list(name: str, value: str, allowed: frozenset) -> list[str]:
    items = _split(value)
    unknown = [item for item in items if item not in allowed]
    if unknown:
        raise _unprocessable(f"Valeur inconnue pour « {name} » : {', '.join(unknown)}")
    return items


def _paris_midnight(name: str, value: str, *, plus_days: int = 0) -> datetime:
    try:
        day = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise _unprocessable(f"Date invalide pour « {name} » (format AAAA-MM-JJ)")
    day = day + timedelta(days=plus_days)
    return datetime(day.year, day.month, day.day, tzinfo=PARIS)


def _like(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _is_id(value: str) -> bool:
    return value.isascii() and value.isdigit() and int(value) <= MAX_BIGINT


def build_audit_filters(params: Mapping[str, str]) -> tuple[str, list]:
    """Construit la clause ``WHERE`` (vide si aucun filtre) et ses arguments positionnels."""
    clauses: list[str] = []
    args: list[Any] = []

    def add(template: str, value: Any) -> None:
        args.append(value)
        clauses.append(template.format(n=len(args)))

    def get(name: str) -> str:
        return (params.get(name) or "").strip()

    if get("kind"):
        add("kind = ANY(${n}::varchar[])", _closed_list("kind", get("kind"), KINDS))
    if get("source"):
        add("source = ANY(${n}::varchar[])", _closed_list("source", get("source"), SOURCES))
    if get("action"):
        add("action = ANY(${n}::varchar[])", _split(get("action")))
    if get("success"):
        flag = get("success").lower()
        if flag not in ("true", "false"):
            raise _unprocessable("« success » doit valoir true ou false")
        add("success = ${n}", flag == "true")

    for name, id_col, name_col in (("actor", "actor_id", "actor_name"), ("target", "target_id", "target_name")):
        value = get(name)
        if not value:
            continue
        if _is_id(value):
            add(id_col + " = ${n}", int(value))
        else:
            add(name_col + " ILIKE ${n}", _like(value))

    if get("channel_id"):
        if not _is_id(get("channel_id")):
            raise _unprocessable("« channel_id » doit être un identifiant numérique")
        add("channel_id = ${n}", int(get("channel_id")))
    if get("from"):
        add("occurred_at >= ${n}", _paris_midnight("from", get("from")))
    if get("to"):
        # « au » est inclus : borne exclusive = minuit Paris du lendemain.
        add("occurred_at < ${n}", _paris_midnight("to", get("to"), plus_days=1))
    if get("q"):
        args.append(_like(get("q")))
        n = len(args)
        clauses.append(
            f"(action ILIKE ${n} OR actor_name ILIKE ${n} OR target_name ILIKE ${n} "
            f"OR channel_name ILIKE ${n} OR details::text ILIKE ${n})"
        )

    return ("WHERE " + " AND ".join(clauses) if clauses else ""), args


def csv_cell(value: str) -> str:
    """Neutralise l'injection de formule : préfixe ``'`` si la valeur commence par = + - @ tab ou CR."""
    if value and value.startswith(_FORMULA_PREFIXES):
        return "'" + value
    return value


def _details(raw: Any) -> dict:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            return {}
    return raw if isinstance(raw, dict) else {}


def _opt_str(value: Any) -> Optional[str]:
    return None if value is None else str(value)


def _event(r: Mapping[str, Any]) -> dict:
    return {
        "id": r["id"],
        "occurred_at": r["occurred_at"].isoformat(),
        "kind": r["kind"],
        "action": r["action"],
        "source": r["source"],
        "actor_id": _opt_str(r["actor_id"]),
        "actor_name": r["actor_name"],
        "target_id": _opt_str(r["target_id"]),
        "target_name": r["target_name"],
        "channel_id": _opt_str(r["channel_id"]),
        "channel_name": r["channel_name"],
        "success": bool(r["success"]),
        "details": _details(r["details"]),
    }


_SELECT = """SELECT id, occurred_at, kind, action, source, actor_id, actor_name, target_id, target_name,
       channel_id, channel_name, success, details
FROM audit_events {where}
ORDER BY occurred_at DESC, id DESC
"""


@router.get("/audit")
async def list_audit(request: Request, page: int = Query(1, ge=1), user: dict = Depends(get_current_user)):
    require_admin(user)
    where, args = build_audit_filters(request.query_params)
    total = int(await db.fetchval(f"SELECT COUNT(*) FROM audit_events {where}", *args) or 0)
    n = len(args)
    rows = await db.fetch(
        _SELECT.format(where=where) + f"LIMIT ${n + 1} OFFSET ${n + 2}",
        *args, PAGE_SIZE, (page - 1) * PAGE_SIZE,
    )
    return {
        "events": [_event(r) for r in rows],
        "total": total,
        "page": page,
        "pages": max(1, -(-total // PAGE_SIZE)),
    }


@router.get("/audit.csv")
async def export_audit_csv(request: Request, user: dict = Depends(get_current_user)):
    require_admin(user)
    where, args = build_audit_filters(request.query_params)
    rows = await db.fetch(
        _SELECT.format(where=where) + f"LIMIT ${len(args) + 1}",
        *args, CSV_MAX_ROWS,
    )

    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";", lineterminator="\r\n")
    writer.writerow(CSV_HEADER)
    for r in rows:
        e = _event(r)
        writer.writerow([
            r["occurred_at"].astimezone(PARIS).strftime("%Y-%m-%d %H:%M:%S"),
            csv_cell(e["kind"]),
            csv_cell(e["action"]),
            csv_cell(e["source"]),
            csv_cell(e["actor_name"] or e["actor_id"] or ""),
            csv_cell(e["target_name"] or e["target_id"] or ""),
            csv_cell(e["channel_name"] or e["channel_id"] or ""),
            "Oui" if e["success"] else "Non",
            csv_cell(json.dumps(e["details"], ensure_ascii=False, separators=(",", ":"))),
        ])

    stamp = datetime.now(PARIS).strftime("%Y%m%d")
    return Response(
        content=("﻿" + buffer.getvalue()).encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="journal-hermes-{stamp}.csv"'},
    )


@router.get("/audit/facets")
async def audit_facets(user: dict = Depends(get_current_user)):
    require_admin(user)
    now = time.monotonic()
    cached = _facets_cache["value"]
    if cached is not None and now - _facets_cache["at"] < FACETS_TTL_S:
        return cached

    pairs = await db.fetch("SELECT DISTINCT kind, action FROM audit_events ORDER BY kind, action")
    kinds: dict[str, list[str]] = {}
    for r in pairs:
        kinds.setdefault(r["kind"], []).append(r["action"])
    channels = await db.fetch(
        """SELECT DISTINCT ON (channel_id) channel_id AS id, channel_name AS name
           FROM audit_events
           WHERE channel_id IS NOT NULL AND channel_name IS NOT NULL
           ORDER BY channel_id, occurred_at DESC"""
    )
    value = {
        "kinds": {k: sorted(v) for k, v in sorted(kinds.items())},
        "channels": sorted(
            ({"id": str(c["id"]), "name": c["name"]} for c in channels),
            key=lambda c: c["name"].lower(),
        ),
    }
    _facets_cache.update(at=now, value=value)
    return value
