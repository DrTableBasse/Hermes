"""Temporisation des créations de salon refusées par Discord (module pur, sans discord).

Après un 403, la création du salon d'une clé n'est pas retentée avant ``delay``
secondes ni avant le prochain rechargement des réglages : sinon chaque message ou
mouvement vocal relancerait une création vouée à l'échec, et Discord bannit l'IP
au-delà de 10 000 réponses 401/403/429 en 10 minutes.
"""
import time
from typing import Callable

DEFAULT_DELAY = 10 * 60


class CreationBackoff:
    def __init__(self, delay: float = DEFAULT_DELAY, clock: Callable[[], float] = time.monotonic):
        self._delay = delay
        self._clock = clock
        self._until: dict[str, float] = {}

    def block(self, key: str) -> None:
        self._until[key] = self._clock() + self._delay

    def is_blocked(self, key: str) -> bool:
        until = self._until.get(key)
        if until is None:
            return False
        if self._clock() >= until:
            del self._until[key]
            return False
        return True

    def clear(self) -> None:
        self._until.clear()
