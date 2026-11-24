"""Règle d'accès aux commandes par rôle (étape 6, tâche 1)."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.command_access import can_use  # noqa: E402


def use(*, owner=False, admin=False, admin_only=False, member=(), allowed=()):
    return can_use(is_owner=owner, is_admin_role=admin, admin_only=admin_only,
                   member_role_ids=set(member), allowed_role_ids=set(allowed))


@pytest.mark.parametrize("admin_only", [False, True])
@pytest.mark.parametrize("allowed", [(), (5,)])
def test_proprietaire_et_admin_toujours_autorises(admin_only, allowed):
    assert use(owner=True, admin_only=admin_only, allowed=allowed)
    assert use(admin=True, admin_only=admin_only, allowed=allowed)


def test_commande_admin_refusee_sans_role_liste():
    assert not use(admin_only=True, member=(1,))
    assert not use(admin_only=True, member=(1,), allowed=(5,))


def test_commande_admin_ouverte_par_un_role_liste():
    assert use(admin_only=True, member=(1, 5), allowed=(5, 6))


def test_commande_normale_liste_vide_ouverte_a_tous():
    assert use(member=())
    assert use(member=(1,))


def test_commande_normale_liste_non_vide_reservee_aux_roles():
    assert use(member=(5,), allowed=(5,))
    assert not use(member=(1,), allowed=(5,))
    assert not use(member=(), allowed=(5,))
