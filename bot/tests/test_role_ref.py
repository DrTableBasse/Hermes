"""Règle de résolution d'un réglage de rôle (constat I4 de la relecture finale)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.role_ref import role_ref  # noqa: E402


def test_stored_id_is_used_alone():
    assert role_ref("123456789012345678", "Administration") == ("id", 123456789012345678)


def test_stored_value_never_falls_back_to_the_default_name():
    # Réglage renseigné mais invalide : aucun repli sur « Administration ».
    assert role_ref("pas-un-id", "Administration") is None


def test_absent_row_falls_back_to_the_default_name():
    assert role_ref(None, "Administration") == ("name", "Administration")
    assert role_ref("", "Modération") == ("name", "Modération")


def test_no_stored_value_and_no_default():
    assert role_ref(None, None) is None
