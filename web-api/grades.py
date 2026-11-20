"""Grades charcutiers : palier de niveau → grade (lecture en base, cache mémoire)."""
import time
from typing import Optional, TypedDict

import database as db

CACHE_TTL = 600  # 10 minutes


class Grade(TypedDict):
    level_min: int
    name: str
    slug: str
    color: str


_cache: Optional[tuple[float, list[Grade]]] = None


def grade_for_level(level: int, grades: list[Grade]) -> Grade:
    """Dernier grade dont ``level_min <= max(level, 1)`` (``grades`` trié par ``level_min``)."""
    level = max(level, 1)
    current = grades[0]
    for grade in grades:
        if grade["level_min"] <= level:
            current = grade
    return current


async def get_grades() -> list[Grade]:
    global _cache
    now = time.monotonic()
    if _cache is not None and now - _cache[0] < CACHE_TTL:
        return _cache[1]
    rows = await db.fetch("SELECT level_min, name, slug, color FROM grades ORDER BY level_min")
    grades = [Grade(level_min=r["level_min"], name=r["name"], slug=r["slug"], color=r["color"]) for r in rows]
    _cache = (now, grades)
    return grades


def clear_grades_cache() -> None:
    global _cache
    _cache = None


def public_grade(level: int, grades: list[Grade]) -> dict:
    """Forme exposée dans les réponses : ``{name, slug, color}``."""
    g = grade_for_level(level, grades)
    return {"name": g["name"], "slug": g["slug"], "color": g["color"]}
