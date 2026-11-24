"""Rang Discord de l'acteur du site et règle de position de l'anti-escalade (§4.1).

Partagé par ``routes/access.py`` (droits du site) et ``routes/roles.py`` (rôles et règles) :
sauf le propriétaire du serveur, un acteur n'agit que sur un rôle **strictement sous**
son rôle le plus haut.
"""
from fastapi import HTTPException

from middleware.auth_middleware import effective_permissions
from routes import admin


async def actor_rank(user: dict, *, with_role_ids: bool = False) -> dict:
    """Rang de l'acteur ``{top_position, is_owner, permissions}`` ; absent du serveur → rang 0.

    ``with_role_ids`` ajoute ``role_ids`` : identifiants (chaînes) des rôles Discord qu'il porte,
    ``@everyone`` exclu (aucun s'il est absent du serveur)."""
    try:
        rank = await admin._bot("get", f"/discord/members/{user['sub']}/rank")
    except HTTPException as e:
        if e.status_code != 404:
            raise
        rank = {"top_position": 0, "is_owner": False}
    actor = {
        "top_position": int(rank["top_position"]),
        "is_owner": bool(rank["is_owner"]),
        "permissions": effective_permissions(user),
    }
    if with_role_ids:
        actor["role_ids"] = [str(r) for r in rank.get("role_ids", [])]
    return actor


def outranks(actor: dict, position: int) -> bool:
    """Vrai si l'acteur peut agir sur un rôle à ``position`` (propriétaire, ou strictement au-dessus)."""
    return actor["is_owner"] or position < actor["top_position"]
