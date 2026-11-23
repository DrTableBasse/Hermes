"""Le catalogue des droits est identique côté web-api et côté site."""
import re
from pathlib import Path

from permissions import PERMISSIONS

TS_FILE = Path(__file__).resolve().parents[2] / "web" / "src" / "lib" / "permissions.ts"
ENTRY = re.compile(r"^\s*'([a-z_]+\.[a-z_]+)':\s*(?:\"([^\"]*)\"|'([^']*)'),?\s*$", re.M)


def _ts_catalog() -> list[tuple[str, str]]:
    return [(m[1], m[2] or m[3]) for m in ENTRY.finditer(TS_FILE.read_text(encoding="utf-8"))]


def test_catalog_has_17_entries():
    assert len(PERMISSIONS) == 17


def test_catalog_matches_web():
    assert _ts_catalog() == list(PERMISSIONS.items())
