"""Tests des grades charcutiers (module pur : ni discord ni config)."""
import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import grades  # noqa: E402
from utils.grades import DEFAULT_GRADES, grade_for_level, next_grade, load_grades  # noqa: E402

GRADES = DEFAULT_GRADES


class FakeDb:
    def __init__(self, rows=None, error=None):
        self.rows, self.error, self.calls = rows, error, 0

    async def fetch(self, query, *args):
        self.calls += 1
        if self.error:
            raise self.error
        return self.rows


@pytest.fixture(autouse=True)
def _fresh_cache():
    grades.clear_grades_cache()
    yield
    grades.clear_grades_cache()


@pytest.mark.parametrize("level,slug", [(0, "recrue"), (1, "recrue"), (2, "recrue"), (3, "caporal"),
    (7, "caporal"), (8, "sergent"), (14, "sergent"), (15, "lieutenant"), (24, "lieutenant"),
    (25, "colonel"), (44, "colonel"), (45, "general"), (200, "general")])
def test_grade_bounds(level, slug):
    assert grade_for_level(level, GRADES)["slug"] == slug


def test_null_level():
    assert grade_for_level(None, GRADES)["slug"] == "recrue"


def test_next_grade():
    assert next_grade(9, GRADES)["slug"] == "lieutenant"
    assert next_grade(1, GRADES)["slug"] == "caporal"
    assert next_grade(45, GRADES) is None


def test_progress_zero_xp():
    level, floor, nxt, ratio = grades.progress(0)
    assert (level, floor, nxt, ratio) == (1, 0, 400, 0.0)


def test_progress_end_of_level_one():
    level, floor, nxt, ratio = grades.progress(399)
    assert level == 1 and floor == 0 and 0 < ratio < 1


def test_progress_level_boundary():
    assert grades.progress(900) == (3, 900, 1600, 0.0)


def test_progress_ratio_bounded_and_null_safe():
    assert grades.progress(None)[3] == 0.0
    assert grades.progress(-50)[3] == 0.0
    for xp in (0, 99, 100, 399, 400, 5000, 10**7):
        assert 0.0 <= grades.progress(xp)[3] <= 1.0


def test_load_grades_reads_and_caches():
    db = FakeDb([{"level_min": 1, "name": "X", "slug": "x", "color": "#000000"}])
    assert [g["slug"] for g in asyncio.run(load_grades(db))] == ["x"]
    asyncio.run(load_grades(db))
    assert db.calls == 1


def test_empty_table_falls_back_and_is_not_cached():
    db = FakeDb([])
    assert len(asyncio.run(load_grades(db))) == 6
    asyncio.run(load_grades(db))
    assert db.calls == 2


def test_db_error_falls_back():
    assert len(asyncio.run(load_grades(FakeDb(error=RuntimeError("table absente"))))) == 6


def test_module_is_pure():
    src = open(grades.__file__, encoding="utf-8").read()
    assert "import discord" not in src and "config" not in src.replace("configur", "")
