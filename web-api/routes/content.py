"""Contenus éditables : jeux de la communauté (public + admin) et pages Markdown (règlement, mentions)."""
import logging
import os
import re
import unicodedata
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Request

import bot_client
import database as db
from bot_client import bot_get, cached
from limiter import limiter
from middleware.auth_middleware import get_current_user, require_permission

log = logging.getLogger(__name__)
router = APIRouter(tags=["content"])

LIVE_TTL = 30
NAME_MAX = 60
TITLE_MAX = 200
BODY_MAX = 50_000
IMAGE_MAX = 500
TAGLINE_MAX = 120
KEY_PATTERN = r"^[a-z0-9-]{1,32}$"
SLUG_PATTERN = r"^[a-z0-9-]{1,64}$"
COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
MEDIA_RE = re.compile(r"^/media/[A-Za-z0-9._-]+$")
GAME_FIELDS = ("name", "color", "image", "tagline", "discord_role_id", "forum_channel_id", "position", "active")


def _has_control(text: str) -> bool:
    return any(unicodedata.category(c) in ("Cc", "Zl", "Zp") for c in text)


def _bad(message: str):
    raise HTTPException(422, message)


# ── Jeux ──────────────────────────────────────────────────────────────────────

async def _players() -> Optional[dict]:
    """``{clé: joueurs}`` d'après ``/live`` du bot ; ``None`` si le bot est muet ou répond de travers."""
    live = await bot_get("/live")
    players = live.get("game_players") if isinstance(live, dict) else None
    return players if isinstance(players, dict) else None


def _count(players: Optional[dict], key: str) -> Optional[int]:
    value = players.get(key) if players else None
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _forum_url(forum_channel_id) -> Optional[str]:
    guild = os.getenv("GUILD_ID", "")
    if not forum_channel_id or not guild.isdigit() or int(guild) <= 0:
        return None
    return f"https://discord.com/channels/{guild}/{forum_channel_id}"


@router.get("/games")
@limiter.limit("60/minute")
async def list_games(request: Request):
    try:
        rows = await db.fetch(
            "SELECT key, name, color, image, tagline, forum_channel_id FROM site_games "
            "WHERE active ORDER BY position, key")
    except Exception as exc:
        log.warning("Lecture des jeux impossible : %s", exc)
        return {"games": [], "stale": True}
    players = await cached("games-live", LIVE_TTL, _players)
    return {"games": [
        {"key": r["key"], "name": r["name"], "color": r["color"], "image": r["image"], "tagline": r["tagline"],
         "players": _count(players, r["key"]), "forum_url": _forum_url(r["forum_channel_id"])}
        for r in rows
    ]}


def _clean_color(value: Any) -> str:
    if not isinstance(value, str) or not COLOR_RE.fullmatch(value):
        _bad("Couleur invalide (format #RRGGBB)")
    return value.upper()


def _clean_name(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        _bad("Nom requis")
    value = value.strip()
    if len(value) > NAME_MAX or _has_control(value):
        _bad(f"Nom : {NAME_MAX} caractères maximum, sur une ligne")
    return value


def _clean_image(value: Any) -> Optional[str]:
    if value is None or value == "":
        return None
    if not isinstance(value, str) or len(value) > IMAGE_MAX:
        _bad("Visuel invalide")
    # Chemin local seulement : la CSP du site (img-src) n'autorise pas d'hôte d'images arbitraire.
    if MEDIA_RE.fullmatch(value) and ".." not in value:
        return value
    _bad("Visuel : chemin /media/… attendu")


def _clean_tagline(value: Any) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        _bad("Accroche invalide")
    value = value.strip()
    if not value:
        return None
    if len(value) > TAGLINE_MAX or _has_control(value):
        _bad(f"Accroche : {TAGLINE_MAX} caractères maximum, sur une ligne")
    return value


def _clean_snowflake(value: Any, label: str) -> Optional[int]:
    if value is None or value == "":
        return None
    if isinstance(value, bool) or not isinstance(value, (int, str)) or not str(value).isdigit():
        _bad(f"{label} invalide")
    number = int(value)
    if not 0 < number < 2**63:
        _bad(f"{label} invalide")
    return number


def _clean_position(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 10_000:
        _bad("Position invalide")
    return value


def _clean_active(value: Any) -> bool:
    if not isinstance(value, bool):
        _bad("Actif doit être un booléen")
    return value


_CLEANERS = {
    "name": _clean_name,
    "color": _clean_color,
    "image": _clean_image,
    "tagline": _clean_tagline,
    "discord_role_id": lambda v: _clean_snowflake(v, "Rôle"),
    "forum_channel_id": lambda v: _clean_snowflake(v, "Forum"),
    "position": _clean_position,
    "active": _clean_active,
}


def _clean_game(body: Any, *, partial: bool) -> dict:
    """Valide les champs fournis d'un jeu ; à la création ``name`` et ``color`` sont requis ; 422 sinon."""
    if not isinstance(body, dict):
        _bad("Corps invalide")
    if not partial:
        for required in ("name", "color"):
            if required not in body:
                _bad(f"Champ « {required} » requis")
    return {k: _CLEANERS[k](body[k]) for k in GAME_FIELDS if k in body}


@router.get("/admin/games")
async def admin_list_games(user: dict = Depends(get_current_user)):
    """Tous les jeux, désactivés compris, avec les champs éditables (rôle, forum, position)."""
    require_permission(user, "games.manage")
    rows = await db.fetch(
        "SELECT key, name, color, image, tagline, discord_role_id, forum_channel_id, position, active "
        "FROM site_games ORDER BY position, key")

    def snowflake(value):
        return str(value) if value else None

    return {"games": [
        {"key": r["key"], "name": r["name"], "color": r["color"], "image": r["image"], "tagline": r["tagline"],
         "discord_role_id": snowflake(r["discord_role_id"]), "forum_channel_id": snowflake(r["forum_channel_id"]),
         "position": r["position"], "active": r["active"]}
        for r in rows
    ]}


@router.post("/admin/games", status_code=201)
async def create_game(body: dict, user: dict = Depends(get_current_user)):
    require_permission(user, "games.manage")
    key = body.get("key")
    if not isinstance(key, str) or not re.fullmatch(KEY_PATTERN, key):
        _bad("Clé invalide ([a-z0-9-], 1 à 32 caractères)")
    fields = _clean_game(body, partial=False)
    if await db.fetchval("SELECT 1 FROM site_games WHERE key = $1", key):
        raise HTTPException(409, "Un jeu porte déjà cette clé")
    position = fields.get("position")
    if position is None:
        position = int(await db.fetchval("SELECT COALESCE(MAX(position), 0) + 1 FROM site_games") or 1)
    await db.execute(
        """INSERT INTO site_games (key, name, color, image, discord_role_id, forum_channel_id, position, active,
                                   tagline)
           VALUES ($1, $2, $3, $4, $5, $6, $7, TRUE, $8)""",
        key, fields["name"], fields["color"], fields.get("image"), fields.get("discord_role_id"),
        fields.get("forum_channel_id"), position, fields.get("tagline"))
    return {"ok": True, "key": key}


@router.put("/admin/games/{key}")
async def update_game(body: dict, key: str = Path(pattern=KEY_PATTERN),
                      user: dict = Depends(get_current_user)):
    require_permission(user, "games.manage")
    fields = _clean_game(body, partial=True)
    if not await db.fetchval("SELECT 1 FROM site_games WHERE key = $1", key):
        raise HTTPException(404, "Jeu inconnu")
    if fields:
        sets = ", ".join(f"{col} = ${i}" for i, col in enumerate(fields, start=2))  # colonnes : liste blanche
        await db.execute(f"UPDATE site_games SET {sets} WHERE key = $1", key, *fields.values())
        bot_client._cache.pop("staff", None)  # l'état-major n'affiche que les jeux actifs
    return {"ok": True}


@router.delete("/admin/games/{key}")
async def deactivate_game(key: str = Path(pattern=KEY_PATTERN), user: dict = Depends(get_current_user)):
    require_permission(user, "games.manage")
    if not await db.fetchval("UPDATE site_games SET active = FALSE WHERE key = $1 RETURNING 1", key):
        raise HTTPException(404, "Jeu inconnu")
    bot_client._cache.pop("staff", None)
    return {"ok": True}


# ── Pages ─────────────────────────────────────────────────────────────────────

@router.get("/pages/{slug}")
@limiter.limit("60/minute")
async def get_page(request: Request, slug: str = Path(pattern=SLUG_PATTERN)):
    try:
        row = await db.fetchrow("SELECT slug, title, body_md, updated_at FROM site_pages WHERE slug = $1", slug)
    except Exception as exc:
        log.warning("Lecture de la page %s impossible : %s", slug, exc)
        raise HTTPException(503, "Page indisponible")
    if not row:
        raise HTTPException(404, "Page inconnue")
    updated = row["updated_at"]
    return {"slug": row["slug"], "title": row["title"] or "", "body_md": row["body_md"] or "",
            "updated_at": updated.isoformat() if updated else None}


@router.put("/admin/pages/{slug}")
async def update_page(body: dict, slug: str = Path(pattern=SLUG_PATTERN),
                      user: dict = Depends(get_current_user)):
    require_permission(user, "content.edit")
    title, body_md = body.get("title"), body.get("body_md")
    if not isinstance(title, str) or not title.strip() or len(title.strip()) > TITLE_MAX or _has_control(title):
        _bad(f"Titre requis ({TITLE_MAX} caractères maximum, sur une ligne)")
    if not isinstance(body_md, str) or len(body_md) > BODY_MAX:
        _bad(f"Contenu requis ({BODY_MAX} caractères maximum)")
    if not await db.fetchval(
            "UPDATE site_pages SET title = $2, body_md = $3, updated_by = $4, updated_at = NOW() "
            "WHERE slug = $1 RETURNING 1", slug, title.strip(), body_md, int(user["sub"])):
        raise HTTPException(404, "Page inconnue")
    return {"ok": True}
