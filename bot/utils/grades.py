"""Grades charcutiers : palier de niveau → grade (lecture en base, cache mémoire).

Même règle que ``web-api/grades.py`` : ``grade_for_level`` renvoie le dernier
grade dont ``level_min <= max(level, 1)``, avec un repli codé en dur si la
table est vide ou absente (le repli n'est jamais mis en cache).
"""
import logging
import time
from typing import Optional, TypedDict

logger = logging.getLogger(__name__)

CACHE_TTL = 600  # 10 minutes


class Grade(TypedDict):
    level_min: int
    name: str
    slug: str
    color: str


# Repli identique aux lignes de la migration 014.
DEFAULT_GRADES: list[Grade] = [
    Grade(level_min=m, name=n, slug=s, color=c) for m, n, s, c in [
        (1, "Recrue Cocktail", "recrue", "#9A97B8"),
        (3, "Caporal Chipolata", "caporal", "#3BD16F"),
        (8, "Sergent Merguez", "sergent", "#FF8A3D"),
        (15, "Lieutenant Toulouse", "lieutenant", "#4D7CFF"),
        (25, "Colonel Saucisson", "colonel", "#3FE0F0"),
        (45, "Général Saucisse", "general", "#9B6BFF"),
    ]
]

_cache: Optional[tuple[float, list[Grade]]] = None


def grade_for_level(level: Optional[int], grades: list[Grade]) -> Grade:
    """Dernier grade dont ``level_min <= max(level, 1)`` (``grades`` trié par ``level_min``)."""
    level = max(int(level or 0), 1)
    current = grades[0]
    for grade in grades:
        if grade["level_min"] <= level:
            current = grade
    return current


def next_grade(level: Optional[int], grades: list[Grade]) -> Optional[Grade]:
    """Premier grade dont le palier dépasse ``level`` ; ``None`` au grade maximal."""
    level = max(int(level or 0), 1)
    for grade in grades:
        if grade["level_min"] > level:
            return grade
    return None


async def load_grades(db) -> list[Grade]:
    """Grades en base triés par palier, cache 10 min ; repli codé en dur sans cache."""
    global _cache
    now = time.monotonic()
    if _cache is not None and now - _cache[0] < CACHE_TTL:
        return _cache[1]
    try:
        rows = await db.fetch("SELECT level_min, name, slug, color FROM grades ORDER BY level_min")
    except Exception as exc:
        logger.warning("Lecture des grades impossible (%s) : repli sur les grades par défaut", exc)
        return list(DEFAULT_GRADES)
    if not rows:
        logger.warning("Table grades vide : repli sur les grades par défaut")
        return list(DEFAULT_GRADES)
    grades = [Grade(level_min=r["level_min"], name=r["name"], slug=r["slug"], color=r["color"]) for r in rows]
    _cache = (now, grades)
    return grades


def clear_grades_cache() -> None:
    global _cache
    _cache = None


def color_to_int(color: str, default: int = 0x9A97B8) -> int:
    """``"#RRGGBB"`` → entier de couleur d'embed ; ``default`` si le texte est invalide."""
    try:
        return int(color.lstrip("#"), 16) if len(color.lstrip("#")) == 6 else default
    except (ValueError, AttributeError):
        return default
