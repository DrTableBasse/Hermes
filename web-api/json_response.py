"""Réponse JSON qui transmet les identifiants Discord en chaînes.

Les snowflakes Discord (64 bits) dépassent 2**53 - 1 et perdent en précision
lorsque JavaScript les lit comme des nombres : tout entier trop grand est donc
sérialisé en chaîne.
"""
import json
from typing import Any

from fastapi.responses import JSONResponse

MAX_SAFE_INT = 2**53 - 1


def stringify_big_ints(obj: Any) -> Any:
    """Convertit en ``str`` tout ``int`` (hors ``bool``) dont ``abs(v) > 2**53 - 1``, récursivement."""
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, int):
        return str(obj) if abs(obj) > MAX_SAFE_INT else obj
    if isinstance(obj, dict):
        return {k: stringify_big_ints(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [stringify_big_ints(v) for v in obj]
    return obj


class SnowflakeJSONResponse(JSONResponse):
    def render(self, content: Any) -> bytes:
        return json.dumps(
            stringify_big_ints(content),
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
