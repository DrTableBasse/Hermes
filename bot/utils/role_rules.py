"""Moteur pur des règles de rôles automatiques : aucune base, aucun Discord."""
from __future__ import annotations

from dataclasses import dataclass

CONDITIONS: frozenset[str] = frozenset({
    "voice_hours", "messages", "level", "grade",
    "achievement", "streak_days", "bumps", "invites",
})


@dataclass
class Rule:
    id: int
    condition_type: str
    condition_value: str
    role_id: int | None = None
    remove_when_lost: bool = False
    exclusive_group: str | None = None
    active: bool = True
    reconcile: bool = False
    create_role_name: str | None = None
    create_role_color: int | None = None


@dataclass
class MemberStats:
    voice_hours: float = 0.0
    messages: int = 0
    level: int = 0
    streak_days: int = 0
    bumps: int = 0
    invites: int = 0
    achievements: frozenset[int] = frozenset()


def _threshold(rule: Rule, grades: dict[str, int]) -> float | None:
    """Seuil numérique d'une règle (None si non numérique ou grade inconnu)."""
    if rule.condition_type == "grade":
        level = grades.get(rule.condition_value)
        return None if level is None else float(level)
    if rule.condition_type == "achievement":
        return None
    try:
        return float(rule.condition_value)
    except ValueError:
        return None


def matches(rule: Rule, stats: MemberStats, grades: dict[str, int]) -> bool:
    ctype = rule.condition_type
    if ctype == "achievement":
        try:
            return int(rule.condition_value) in stats.achievements
        except ValueError:
            return False
    if ctype not in CONDITIONS:
        return False
    threshold = _threshold(rule, grades)
    if threshold is None:
        return False
    value = stats.level if ctype == "grade" else getattr(stats, ctype)
    return value >= threshold


def plan_changes(
    rules: list[Rule],
    stats: MemberStats,
    member_role_ids: set[int],
    grades: dict[str, int],
) -> tuple[set[int], set[int]]:
    """Retourne (rôles à ajouter, rôles à retirer) pour un membre."""
    usable = [r for r in rules if r.active and r.role_id is not None]
    matched = [r for r in usable if matches(r, stats, grades)]
    wanted = {r.role_id for r in matched}

    # Groupes exclusifs : le seuil le plus élevé gagne, les autres perdent.
    losers: set[int] = set()
    for group in {r.exclusive_group for r in usable if r.exclusive_group}:
        in_group = [r for r in usable if r.exclusive_group == group]
        won = [r for r in in_group if r in matched]
        if not won:
            continue
        winner = max(won, key=lambda r: (_threshold(r, grades) or 0.0, r.id))
        for r in in_group:
            if r.role_id != winner.role_id:
                losers.add(r.role_id)
        wanted -= losers - {winner.role_id}

    to_add = wanted - member_role_ids
    to_remove = {r.role_id for r in usable
                 if r not in matched and r.remove_when_lost}
    to_remove |= losers
    to_remove &= member_role_ids
    to_remove -= wanted
    return to_add, to_remove


def find_conflicts(rules: list[Rule]) -> list[str]:
    """Deux règles actives sur le même rôle dont l'une a « retirer si perdu »."""
    by_role: dict[int, list[Rule]] = {}
    for r in rules:
        if r.active and r.role_id is not None:
            by_role.setdefault(r.role_id, []).append(r)
    return [
        f"Le rôle {role_id} est visé par {len(group)} règles actives dont "
        "l'une le retire à la perte de la condition : elles se contrediraient."
        for role_id, group in by_role.items()
        if len(group) > 1 and any(r.remove_when_lost for r in group)
    ]
