"""Règle d'accès aux commandes Hermes selon les rôles autorisés (fonction pure)."""


def can_use(*, is_owner: bool, is_admin_role: bool, admin_only: bool,
            member_role_ids: set[int], allowed_role_ids: set[int]) -> bool:
    """Le membre peut-il utiliser la commande ?

    Propriétaire et rôle admin : toujours. Commande réservée aux admins : seulement via
    un rôle de la liste. Autre commande : liste vide = tout le monde, sinon via la liste.
    """
    if is_owner or is_admin_role:
        return True
    if admin_only:
        return bool(member_role_ids & allowed_role_ids)
    return not allowed_role_ids or bool(member_role_ids & allowed_role_ids)
