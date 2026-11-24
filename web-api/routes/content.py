"""Contenus éditables : jeux de la communauté (public + admin) et pages Markdown (règlement, mentions)."""
import logging
import os
import re
import unicodedata
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Request

import asyncpg
import httpx
from pydantic import BaseModel

import bot_client
import database as db
from bot_client import bot_get, cached
from game_rules import NOTIFICATION_EMOJIS, validate_command_name, validate_emoji
from limiter import limiter
from middleware.auth_middleware import get_current_user, require_permission
from routes import admin

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
GAME_FIELDS = ("name", "color", "image", "tagline", "discord_role_id", "forum_channel_id", "position", "active",
               "emoji", "command_name", "lfg_cooldown")
GAME_REQUIRED = ("name", "color", "emoji", "command_name")
EMOJI_MAX = 32
LFG_COOLDOWN_MIN, LFG_COOLDOWN_MAX = 60, 86_400  # 1 min à 24 h (0 vaudrait « défaut » côté bot)
# Délais des appels au bot pour les jeux : rôle + forum + écritures, ou un forum par jeu. Le cog
# sérialise ces actions (verrou) et discord.py attend en silence la fin d'une limite de débit :
# les 10 s par défaut de ``admin._bot`` pourraient être dépassées alors que le bot termine.
GAME_ACTION_TIMEOUT = 30.0
GAME_RESYNC_TIMEOUT = 60.0
GAME_CHECK_TIMEOUT = 5.0
RESYNC_ADMIN_ONLY = ("Réservé aux administrateurs : les forums de jeux sont ouverts aux rôles "
                     "« staff_roles », qui donnent des droits")


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
            "SELECT key, name, color, image, tagline, forum_channel_id, command_name, provisioned, archived "
            "FROM site_games WHERE active ORDER BY position, key")
    except Exception as exc:
        log.warning("Lecture des jeux impossible : %s", exc)
        return {"games": [], "stale": True}
    players = await cached("games-live", LIVE_TTL, _players)
    return {"games": [
        {"key": r["key"], "name": r["name"], "color": r["color"], "image": r["image"], "tagline": r["tagline"],
         "players": _count(players, r["key"]), "forum_url": _forum_url(r["forum_channel_id"]),
         # Commande inscrite par le bot (R6 : provisionné et non archivé), sinon None.
         "command_name": r["command_name"] if r["provisioned"] and not r["archived"] else None}
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


def _clean_emoji(value: Any) -> str:
    """Un seul émoji (Unicode ou ``<:nom:id>``) ; l'unicité est vérifiée ensuite (``_check_unique``)."""
    error = validate_emoji(value, set())
    if error:
        _bad(error)
    value = value.strip()
    if len(value) > EMOJI_MAX:  # colonne site_games.emoji VARCHAR(32) (long nom d'émoji personnalisé)
        _bad(f"Émoji trop long : {EMOJI_MAX} caractères maximum")
    return value


def _clean_command_name(value: Any) -> str:
    error = validate_command_name(value, set())
    if error:
        _bad(error)
    return value


def _clean_lfg_cooldown(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) \
            or not LFG_COOLDOWN_MIN <= value <= LFG_COOLDOWN_MAX:
        _bad(f"Délai entre deux appels : nombre de secondes entre {LFG_COOLDOWN_MIN} et {LFG_COOLDOWN_MAX}")
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
    "emoji": _clean_emoji,
    "command_name": _clean_command_name,
    "lfg_cooldown": _clean_lfg_cooldown,
}


def _clean_game(body: Any, *, partial: bool) -> dict:
    """Valide les champs fournis d'un jeu ; à la création ``GAME_REQUIRED`` sont requis ; 422 sinon."""
    if not isinstance(body, dict):
        _bad("Corps invalide")
    if not partial:
        for required in GAME_REQUIRED:
            if required not in body:
                _bad(f"Champ « {required} » requis")
    return {k: _CLEANERS[k](body[k]) for k in GAME_FIELDS if k in body}


# ── Appels au bot pour les jeux ──────────────────────────────────────────────

async def _game_bot(method: str, path: str, *, timeout: float, **kwargs) -> dict:
    """``admin._bot`` avec un délai adapté ; réseau et délai traduits en français (503 / 504)."""
    try:
        return await admin._bot(method, path, timeout=timeout, **kwargs)
    except httpx.TimeoutException:
        raise HTTPException(504, "Le bot n'a pas répondu à temps : l'action se termine peut-être encore. "
                                 "Rechargez la page pour voir l'état du jeu.")
    except httpx.HTTPError:
        raise HTTPException(503, "Bot injoignable : réessayez dans un instant")


async def _game_write(action: str, user: dict, game: dict, method: str, path: str, *,
                      timeout: float = GAME_ACTION_TIMEOUT, details: Optional[dict] = None) -> dict:
    """Action Discord d'un jeu via le bot ; un échec est journalisé (``success=false``) puis relayé."""
    details = {"key": game["key"], **(details or {})}
    try:
        return await _game_bot(method, path, timeout=timeout)
    except HTTPException as e:
        await admin._log(action, int(user["sub"]), details={**details, "error": str(e.detail)},
                         success=False, target_name=game["name"])
        raise


async def _reload_bot() -> bool:
    """Demande au bot de relire ``site_games`` ; un échec n'annule pas l'écriture déjà faite."""
    try:
        await _game_bot("post", "/games/reload", timeout=GAME_CHECK_TIMEOUT)
        return True
    except HTTPException as e:  # bot injoignable : il relira au redémarrage
        log.warning("Rechargement des jeux refusé par le bot : %s", e.detail)
        return False


async def _check_unique(key: str, fields: dict) -> None:
    """Nom de commande et émoji libres (422 sinon) : autres jeux, commandes du bot, notifications."""
    if "command_name" not in fields and "emoji" not in fields:
        return
    others = await db.fetch("SELECT key, emoji, command_name FROM site_games WHERE key <> $1", key)
    if "command_name" in fields:
        try:
            taken = await _game_bot("get", "/games/taken", timeout=GAME_CHECK_TIMEOUT, params={"exclude": key})
        except HTTPException:
            raise HTTPException(503, f"Bot injoignable : impossible de vérifier que /{fields['command_name']} "
                                     "n'est pas déjà une commande du bot. Réessayez dans un instant.")
        commands = set(taken.get("commands") or ()) | {r["command_name"] for r in others if r["command_name"]}
        error = validate_command_name(fields["command_name"], commands)
        if error:
            _bad(error)
    if "emoji" in fields:
        emojis = set(NOTIFICATION_EMOJIS) | {r["emoji"] for r in others if r["emoji"]}
        error = validate_emoji(fields["emoji"], emojis)
        if error:
            _bad(error)


def _unique_violation(exc: asyncpg.UniqueViolationError, fields: dict):
    """Course avec une autre écriture : index unique du nom de commande, ou clé déjà prise."""
    if "command_name" in (getattr(exc, "constraint_name", None) or ""):
        _bad(f"La commande /{fields.get('command_name')} existe déjà.")
    raise HTTPException(409, "Un jeu porte déjà cette clé")


async def _game(key: str) -> dict:
    row = await db.fetchrow("SELECT key, name FROM site_games WHERE key = $1", key)
    if not row:
        raise HTTPException(404, "Jeu inconnu")
    return dict(row)


# ── Routes d'administration des jeux ─────────────────────────────────────────

@router.get("/admin/games")
async def admin_list_games(user: dict = Depends(get_current_user)):
    """Tous les jeux, désactivés compris, avec les champs éditables et l'état Discord.

    ``status`` : ``{"role", "forum", "command"}`` (``ok`` / ``missing`` / ``none``) d'après le bot,
    ``None`` si le bot est injoignable ou ne connaît pas encore le jeu (``bot_reachable``).
    """
    require_permission(user, "games.manage")
    rows = await db.fetch(
        "SELECT key, name, color, image, tagline, discord_role_id, forum_channel_id, position, active, "
        "emoji, command_name, lfg_cooldown, provisioned, archived "
        "FROM site_games ORDER BY position, key")
    live = await bot_get("/games/status", timeout=GAME_CHECK_TIMEOUT)
    statuses = live.get("games") if isinstance(live, dict) and isinstance(live.get("games"), dict) else None

    def snowflake(value):
        return str(value) if value else None

    return {"bot_reachable": statuses is not None, "games": [
        {"key": r["key"], "name": r["name"], "color": r["color"], "image": r["image"], "tagline": r["tagline"],
         "discord_role_id": snowflake(r["discord_role_id"]), "forum_channel_id": snowflake(r["forum_channel_id"]),
         "position": r["position"], "active": r["active"],
         "emoji": r["emoji"], "command_name": r["command_name"], "lfg_cooldown": r["lfg_cooldown"],
         "provisioned": r["provisioned"], "archived": r["archived"],
         "status": (statuses or {}).get(r["key"])}
        for r in rows
    ]}


@router.post("/admin/games", status_code=201)
async def create_game(body: dict, user: dict = Depends(get_current_user)):
    """Crée la ligne du jeu (non provisionnée : ni rôle, ni forum, ni commande avant ``/provision``)."""
    require_permission(user, "games.manage")
    key = body.get("key") if isinstance(body, dict) else None
    if not isinstance(key, str) or not re.fullmatch(KEY_PATTERN, key):
        _bad("Clé invalide ([a-z0-9-], 1 à 32 caractères)")
    fields = _clean_game(body, partial=False)
    if await db.fetchval("SELECT 1 FROM site_games WHERE key = $1", key):
        raise HTTPException(409, "Un jeu porte déjà cette clé")
    await _check_unique(key, fields)
    position = fields.get("position")
    if position is None:
        position = int(await db.fetchval("SELECT COALESCE(MAX(position), 0) + 1 FROM site_games") or 1)
    try:
        await db.execute(
            """INSERT INTO site_games (key, name, color, image, discord_role_id, forum_channel_id, position, active,
                                       tagline, emoji, command_name, lfg_cooldown, provisioned, archived)
               VALUES ($1, $2, $3, $4, $5, $6, $7, TRUE, $8, $9, $10, $11, FALSE, FALSE)""",
            key, fields["name"], fields["color"], fields.get("image"), fields.get("discord_role_id"),
            fields.get("forum_channel_id"), position, fields.get("tagline"), fields["emoji"],
            fields["command_name"], fields.get("lfg_cooldown", 3600))
    except asyncpg.UniqueViolationError as e:
        _unique_violation(e, fields)
    await admin._log("game_create", int(user["sub"]), target_name=fields["name"], details={
        "key": key, "name": fields["name"], "emoji": fields["emoji"], "command_name": fields["command_name"]})
    return {"ok": True, "key": key, "bot_reloaded": await _reload_bot()}


@router.put("/admin/games/{key}")
async def update_game(body: dict, key: str = Path(pattern=KEY_PATTERN),
                      user: dict = Depends(get_current_user)):
    require_permission(user, "games.manage")
    fields = _clean_game(body, partial=True)
    game = await _game(key)
    if not fields:
        return {"ok": True, "bot_reloaded": True}
    await _check_unique(key, fields)
    sets = ", ".join(f"{col} = ${i}" for i, col in enumerate(fields, start=2))  # colonnes : liste blanche
    try:
        await db.execute(f"UPDATE site_games SET {sets} WHERE key = $1", key, *fields.values())
    except asyncpg.UniqueViolationError as e:
        _unique_violation(e, fields)
    bot_client._cache.pop("staff", None)  # l'état-major n'affiche que les jeux actifs
    await admin._log("game_update", int(user["sub"]), target_name=game["name"],
                     details={"key": key, "changes": fields})
    return {"ok": True, "bot_reloaded": await _reload_bot()}


@router.delete("/admin/games/{key}")
async def deactivate_game(key: str = Path(pattern=KEY_PATTERN), user: dict = Depends(get_current_user)):
    """Désactive : le bot archive (commande retirée, forum masqué au rôle, rôle gardé), puis le jeu
    quitte le site public (``active = FALSE``)."""
    require_permission(user, "games.manage")
    game = await _game(key)
    result = await _game_write("game_archive", user, game, "post", f"/games/{key}/archive")
    await db.execute("UPDATE site_games SET active = FALSE WHERE key = $1", key)
    bot_client._cache.pop("staff", None)
    await admin._log("game_archive", int(user["sub"]), target_name=game["name"], details={"key": key})
    return {"ok": True, "status": result.get("status")}


@router.post("/admin/games/{key}/reactivate")
async def reactivate_game(key: str = Path(pattern=KEY_PATTERN), user: dict = Depends(get_current_user)):
    """Réactive : le bot réinscrit la commande et rouvre le forum au rôle ; le jeu revient sur le site."""
    require_permission(user, "games.manage")
    game = await _game(key)
    result = await _game_write("game_reactivate", user, game, "post", f"/games/{key}/unarchive")
    await db.execute("UPDATE site_games SET active = TRUE WHERE key = $1", key)
    bot_client._cache.pop("staff", None)
    await admin._log("game_reactivate", int(user["sub"]), target_name=game["name"], details={"key": key})
    return {"ok": True, "status": result.get("status")}


@router.post("/admin/games/{key}/provision")
async def provision_game(key: str = Path(pattern=KEY_PATTERN), user: dict = Depends(get_current_user)):
    """Rôle, forum et commande du jeu : réutilisés s'ils existent, créés sinon (idempotent)."""
    require_permission(user, "games.manage")
    game = await _game(key)
    result = await _game_write("game_provision", user, game, "post", f"/games/{key}/provision")
    await admin._log("game_provision", int(user["sub"]), target_name=game["name"], details={
        "key": key, "created": result.get("created", []), "role_id": result.get("role_id"),
        "forum_id": result.get("forum_id"), "command": result.get("command")})
    return result


def _require_admin(user: dict) -> None:
    require_permission(user, "games.manage")
    if not user.get("is_admin"):
        raise HTTPException(403, RESYNC_ADMIN_ONLY)


async def _resync_count() -> int:
    status = await _game_bot("get", "/games/status", timeout=GAME_CHECK_TIMEOUT)
    return int(status.get("resync_forums") or 0)


class ResyncConfirm(BaseModel):
    confirm_forums: int


@router.get("/admin/games/resync-permissions")
async def resync_preview(user: dict = Depends(get_current_user)):
    """Aperçu : nombre de forums de jeux dont les permissions seraient réécrites."""
    _require_admin(user)
    return {"forums": await _resync_count()}


@router.post("/admin/games/resync-permissions")
async def resync_permissions(body: ResyncConfirm, user: dict = Depends(get_current_user)):
    """Réécrit les permissions de tous les forums de jeux (après un changement de ``staff_roles``).

    ``confirm_forums`` : le nombre affiché par l'aperçu ; s'il a changé, 409 sans rien écrire.
    """
    _require_admin(user)
    count = await _resync_count()
    if body.confirm_forums != count:
        raise HTTPException(409, f"Le nombre a changé : {count} forum(s) de jeux concerné(s). "
                                 "Vérifiez puis confirmez à nouveau.")
    actor_id = int(user["sub"])
    try:
        result = await _game_bot("post", "/games/resync-permissions", timeout=GAME_RESYNC_TIMEOUT)
    except HTTPException as e:
        await admin._log("game_resync_permissions", actor_id, success=False,
                         details={"forums": count, "error": str(e.detail)})
        raise
    await admin._log("game_resync_permissions", actor_id, details={"forums": result.get("forums")})
    return {"ok": True, "forums": result.get("forums")}


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
