"""État-major : liste du staff lue par le bot (publique), profils éditables stockés en base."""
import logging
import unicodedata
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Request

import bot_client
import database as db
from bot_client import bot_get, cached
from grades import get_grades, public_grade
from limiter import limiter
from middleware.auth_middleware import get_current_user, require_admin

log = logging.getLogger(__name__)
router = APIRouter(tags=["staff"])

STAFF_TTL = 300
MOTTO_MAX = 140
GAME_MAX = 40
GAMES_MAX = 5
_last_raw: Optional[list] = None  # dernière liste valide renvoyée par le bot


class _Uncacheable(Exception):
    """Réponse dégradée (bot muet, base en échec) : servie telle quelle, jamais mise en cache."""

    def __init__(self, payload: dict):
        super().__init__("état-major dégradé")
        self.payload = payload


def _valid_member(member) -> bool:
    try:
        return isinstance(member, dict) and int(member["id"]) > 0 and bool(member.get("name"))
    except (KeyError, TypeError, ValueError):
        return False


async def _fetch_raw() -> Optional[list]:
    data = await bot_get("/staff")
    if not isinstance(data, list):
        return None
    valid = [m for m in data if _valid_member(m)]
    if len(valid) < len(data):
        log.warning("%d membre(s) du staff mal formé(s) ignoré(s)", len(data) - len(valid))
    return valid


async def _bot_staff() -> tuple[Optional[list], bool]:
    """(liste, périmée) : liste du bot, sinon la dernière connue, sinon ``(None, True)``."""
    global _last_raw
    raw = await cached("staff-raw", STAFF_TTL, _fetch_raw)
    if raw is None:
        return _last_raw, True
    _last_raw = raw
    return raw, False


def _member(m: dict, profile: Optional[dict], level: Optional[int], grade: Optional[dict]) -> dict:
    return {
        "id": str(m["id"]), "name": m["name"], "avatar": m.get("avatar"), "role": m.get("role"),
        "grade": grade, "level": level,
        "motto": profile["motto"] if profile else None,
        "games": list(profile["games"] or []) if profile else [],
    }


async def _build() -> dict:
    raw, stale = await _bot_staff()
    if raw is None:
        raise _Uncacheable({"staff": [], "stale": True})
    ids = [int(m["id"]) for m in raw]
    try:
        profiles = {int(r["user_id"]): r for r in await db.fetch(
            "SELECT user_id, motto, games FROM staff_profiles WHERE user_id = ANY($1::bigint[])", ids)}
        levels = {int(r["user_id"]): int(r["current_level"] or 0) for r in await db.fetch(
            "SELECT user_id, current_level FROM user_xp WHERE user_id = ANY($1::bigint[])", ids)}
        grades = await get_grades()
    except Exception as exc:
        # Aucun chiffre inventé : niveau et grade restent ``None``.
        log.warning("Profils du staff indisponibles : %s", exc)
        raise _Uncacheable({"staff": [_member(m, None, None, None) for m in raw], "stale": True})
    staff = [_member(m, profiles.get(int(m["id"])), levels.get(int(m["id"]), 0),
                     public_grade(levels.get(int(m["id"]), 0), grades)) for m in raw]
    if stale:
        raise _Uncacheable({"staff": staff, "stale": True})
    return {"staff": staff}


@router.get("/staff")
@limiter.limit("60/minute")
async def get_staff(request: Request):
    try:
        return await cached("staff", STAFF_TTL, _build)
    except _Uncacheable as degraded:
        return degraded.payload


# ── Écriture des profils ──────────────────────────────────────────────────────

def _has_control(text: str) -> bool:
    """Caractère de contrôle (dont retours à la ligne) ou séparateur de ligne/paragraphe."""
    return any(unicodedata.category(c) in ("Cc", "Zl", "Zp") for c in text)


def _clean_profile(body: Any) -> tuple[Optional[str], list[str]]:
    """Valide ``{motto, games}`` ; 422 sinon. Phrase vide → ``None``."""
    if not isinstance(body, dict):
        raise HTTPException(422, "Corps invalide")
    motto = body.get("motto")
    if motto is not None:
        if not isinstance(motto, str):
            raise HTTPException(422, "La phrase doit être un texte")
        motto = motto.strip() or None
        if motto and len(motto) > MOTTO_MAX:
            raise HTTPException(422, f"La phrase ne peut pas dépasser {MOTTO_MAX} caractères")
        if motto and _has_control(motto):
            raise HTTPException(422, "La phrase ne peut pas contenir de caractère de contrôle")
    games = body.get("games", [])
    if not isinstance(games, list) or len(games) > GAMES_MAX:
        raise HTTPException(422, f"{GAMES_MAX} jeux maximum")
    if not all(isinstance(g, str) and g.strip() for g in games):
        raise HTTPException(422, "Chaque jeu doit être un texte non vide")
    cleaned: list[str] = []
    for game in (g.strip() for g in games):
        if len(game) > GAME_MAX:
            raise HTTPException(422, f"Un jeu ne peut pas dépasser {GAME_MAX} caractères")
        if _has_control(game):
            raise HTTPException(422, "Un jeu ne peut pas contenir de caractère de contrôle")
        if game.casefold() not in {g.casefold() for g in cleaned}:
            cleaned.append(game)
    return motto, cleaned


async def _check_games(games: list[str]) -> None:
    """Chaque jeu doit être la clé d'un jeu actif de ``site_games`` ; 422 sinon."""
    if not games:
        return
    try:
        rows = await db.fetch("SELECT key FROM site_games WHERE active AND key = ANY($1::text[])", games)
    except Exception as exc:
        log.warning("Vérification des jeux impossible : %s", exc)
        raise HTTPException(503, "Liste des jeux indisponible")
    unknown = [g for g in games if g not in {r["key"] for r in rows}]
    if unknown:
        raise HTTPException(422, f"Jeu inconnu ou désactivé : {unknown[0]}")


async def _save(user_id: int, motto: Optional[str], games: list[str]) -> None:
    await db.execute(
        """INSERT INTO staff_profiles (user_id, motto, games, updated_at) VALUES ($1, $2, $3, NOW())
           ON CONFLICT (user_id) DO UPDATE
           SET motto = EXCLUDED.motto, games = EXCLUDED.games, updated_at = NOW()""",
        user_id, motto, games,
    )
    bot_client._cache.pop("staff", None)  # la liste publique reflète l'édition sans attendre le TTL


@router.put("/staff/me")
@limiter.limit("20/minute")
async def put_my_profile(request: Request, body: dict, user: dict = Depends(get_current_user)):
    motto, games = _clean_profile(body)
    await _check_games(games)
    raw, _ = await _bot_staff()
    if raw is None:
        raise HTTPException(503, "Liste du staff indisponible")
    me = int(user["sub"])
    if me not in {int(m["id"]) for m in raw}:
        raise HTTPException(403, "Réservé à l'état-major")
    await _save(me, motto, games)
    return {"ok": True}


@router.put("/admin/staff/{user_id}")
async def put_staff_profile(body: dict, user_id: int = Path(gt=0, lt=2**63),
                            user: dict = Depends(get_current_user)):
    require_admin(user)
    motto, games = _clean_profile(body)
    await _check_games(games)
    raw, _ = await _bot_staff()
    if raw is None:
        raise HTTPException(503, "Liste du staff indisponible")
    if user_id not in {int(m["id"]) for m in raw}:
        raise HTTPException(404, "Membre absent de l'état-major")
    await _save(user_id, motto, games)
    return {"ok": True}
