"""Catalogue des permissions Discord (étape 6, tâche 1) : exhaustivité, conversions, anti-escalade."""
import os
import sys

import discord
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.permission_catalog import (  # noqa: E402
    FAMILIES, escalation_error, flags_to_value, value_to_flags,
)

VALID = discord.Permissions.VALID_FLAGS
ALL_KEYS = [k for _, items in FAMILIES for k, _ in items]


def bits(**kw) -> int:
    return discord.Permissions(**kw).value


def test_chaque_cle_est_unique_et_valide():
    assert len(ALL_KEYS) == len(set(ALL_KEYS))
    assert set(ALL_KEYS) <= set(VALID)


def test_chaque_bit_de_discord_py_est_dans_exactement_une_famille():
    # Les alias partagent un bit : on compte par bit, pas par nom.
    couverts = [VALID[k] for k in ALL_KEYS]
    assert len(couverts) == len(set(couverts))
    assert set(couverts) == set(VALID.values())


def test_libelles_non_vides_et_familles_attendues():
    assert [f for f, _ in FAMILIES] == ["Général", "Membres", "Messages", "Vocal", "Événements", "Avancé"]
    assert all(label.strip() for _, items in FAMILIES for _, label in items)


def test_conversions_aller_retour():
    flags = {"ban_members", "send_messages", "connect"}
    value = flags_to_value(flags)
    assert value == bits(ban_members=True, send_messages=True, connect=True)
    assert value_to_flags(value) == flags
    assert flags_to_value([]) == 0 and value_to_flags(0) == set()


def test_alias_donne_le_drapeau_canonique():
    assert value_to_flags(bits(read_messages=True)) == {"view_channel"}


def test_drapeau_inconnu_refuse():
    with pytest.raises(ValueError):
        flags_to_value(["inconnu"])


def test_toutes_les_permissions_se_convertissent():
    assert flags_to_value(ALL_KEYS) == discord.Permissions.all().value
    assert value_to_flags(discord.Permissions.all().value) == set(ALL_KEYS)


BAN, KICK, ADMIN = bits(ban_members=True), bits(kick_members=True), bits(administrator=True)


def test_proprietaire_peut_tout():
    assert escalation_error(0, True, 0, ADMIN | BAN) is None


def test_activer_sans_posseder_refuse():
    err = escalation_error(KICK, False, 0, BAN)
    assert err and "Bannir des membres" in err and "accorder" in err


def test_retirer_sans_posseder_refuse():
    err = escalation_error(KICK, False, BAN | KICK, KICK)
    assert err and "Bannir des membres" in err and "retirer" in err


def test_activer_en_possedant_accepte():
    assert escalation_error(BAN | KICK, False, KICK, KICK | BAN) is None


def test_aucun_changement_accepte():
    assert escalation_error(0, False, BAN, BAN) is None


def test_administrateur_acteur_peut_tout_sauf_accorder_administrateur():
    assert escalation_error(ADMIN, False, 0, BAN | KICK) is None
    assert escalation_error(ADMIN, False, BAN, 0) is None
    err = escalation_error(ADMIN, False, BAN, BAN | ADMIN)
    assert err and "propriétaire" in err


def test_retirer_administrateur_sans_etre_admin_refuse():
    err = escalation_error(BAN, False, ADMIN, 0)
    assert err and "Administrateur" in err and "retirer" in err
    assert escalation_error(ADMIN, False, ADMIN, 0) is None
