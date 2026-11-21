"""Règle de résolution d'un réglage de rôle (module pur, sans discord).

Même règle que le site (``web-v2/src/lib/auth.ts``) : un réglage renseigné désigne
un rôle **par identifiant**, et lui seul ; le repli sur un nom ne vaut que tant que
la ligne est absente de ``bot_settings``. Sans cela, quiconque crée un rôle nommé
« Administration » après la suppression du rôle réglé en obtiendrait les droits.
"""
from typing import Optional, Tuple

RoleRef = Tuple[str, object]  # ("id", int) | ("name", str)


def role_ref(stored: Optional[str], default: Optional[str]) -> Optional[RoleRef]:
    """``stored`` : valeur enregistrée (``None``/vide : ligne absente) ; ``default`` : registre."""
    if stored:
        value = stored.strip()
        return ("id", int(value)) if value.isdigit() else None
    if default:
        return ("id", int(default)) if default.isdigit() else ("name", default)
    return None
