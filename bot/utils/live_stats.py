"""Calculs purs de la caserne en direct (aucun import discord, testable seul)."""
from dataclasses import dataclass, field
from typing import Iterable, Optional

AVATAR_LIMIT = 5


class MessageCounter:
    """Compteur en mémoire des messages, remis à zéro à chaque relevé."""

    def __init__(self):
        self._count = 0

    def increment(self) -> None:
        self._count += 1

    def take(self) -> int:
        count, self._count = self._count, 0
        return count

    def give_back(self, count: int) -> None:
        """Restitue un compte prélevé quand l'écriture du relevé a échoué."""
        self._count += count


@dataclass
class MemberView:
    is_bot: bool
    online: bool
    in_voice: bool
    avatar_url: Optional[str] = None
    role_names: frozenset = field(default_factory=frozenset)


def summarize(members: Iterable[MemberView], game_roles: dict[str, str],
              avatar_limit: int = AVATAR_LIMIT) -> dict:
    """Agrège les membres humains : effectifs, avatars en vocal, joueurs par jeu.

    ``game_roles`` : clé de jeu -> nom du rôle.
    """
    total = online = in_voice = 0
    avatars: list[str] = []
    players = {key: 0 for key in game_roles}
    for m in members:
        if m.is_bot:
            continue
        total += 1
        online += m.online
        if m.in_voice:
            in_voice += 1
            if m.avatar_url and len(avatars) < avatar_limit:
                avatars.append(m.avatar_url)
        for key, role in game_roles.items():
            if role in m.role_names:
                players[key] += 1
    return {"members": total, "online": online, "in_voice": in_voice,
            "voice_avatars": avatars, "game_players": players}
