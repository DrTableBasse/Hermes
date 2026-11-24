"""Salons (étape 5, tâche 1) : modèles d'accès, plan de changements, jeton d'aperçu."""
import os
import sys

import discord
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.channel_templates import (  # noqa: E402
    TEMPLATES, Overwrite, plan, preview_token, template_overwrites,
)

EVERYONE, BOT = 1, 2
R1, R2 = 10, 11
STAFF1, STAFF2 = 20, 21


def bits(**kw) -> int:
    return discord.Permissions(**kw).value


VIEW = bits(view_channel=True)
TEXT_WRITE = bits(send_messages=True, create_public_threads=True,
                  create_private_threads=True, send_messages_in_threads=True)
VOICE_WRITE = bits(connect=True, speak=True)
FORUM_WRITE = bits(send_messages=True, create_public_threads=True,
                   send_messages_in_threads=True)
MANAGE = bits(manage_messages=True)


def build(template, ctype="text", roles=(R1,), staff=(STAFF1,)):
    return template_overwrites(template, EVERYONE, BOT, list(roles), list(staff), ctype)


def test_templates():
    assert TEMPLATES == ("public", "role_required", "announcements", "staff")


def test_public_aucune_surcharge_everyone_et_bot_toujours_present():
    ow = build("public")
    assert EVERYONE not in ow and R1 not in ow and STAFF1 not in ow
    assert ow[BOT] == Overwrite(BOT, "member", VIEW | TEXT_WRITE | MANAGE, 0)


def test_role_requis_texte():
    ow = build("role_required", roles=(R1, R2))
    assert ow[EVERYONE] == Overwrite(EVERYONE, "role", 0, VIEW)
    for r in (R1, R2):
        assert ow[r] == Overwrite(r, "role", VIEW | TEXT_WRITE, 0)


def test_role_requis_vocal_connect_speak():
    ow = build("role_required", "voice")
    assert ow[R1].allow == VIEW | VOICE_WRITE
    assert ow[EVERYONE].deny == VIEW
    assert ow[BOT].allow & VOICE_WRITE == VOICE_WRITE


def test_role_requis_forum():
    assert build("role_required", "forum")[R1].allow == VIEW | FORUM_WRITE


def test_annonces_texte():
    ow = build("announcements")
    assert ow[EVERYONE] == Overwrite(EVERYONE, "role", VIEW, TEXT_WRITE)
    assert ow[R1] == Overwrite(R1, "role", TEXT_WRITE, 0)


def test_annonces_forum_et_vocal():
    assert build("announcements", "forum")[EVERYONE].deny == FORUM_WRITE
    assert build("announcements", "voice")[EVERYONE].deny == VOICE_WRITE


def test_staff_texte_et_vocal():
    ow = build("staff", roles=())
    assert ow[EVERYONE] == Overwrite(EVERYONE, "role", 0, VIEW)
    assert ow[STAFF1].allow == VIEW | TEXT_WRITE | MANAGE
    assert ow[STAFF1].deny == 0
    assert R1 not in ow
    assert build("staff", "voice")[STAFF1].allow & VOICE_WRITE == VOICE_WRITE


def test_type_ou_modele_inconnu():
    with pytest.raises(ValueError):
        build("inconnu")
    with pytest.raises(ValueError):
        build("public", "stage")


def test_plan_ajout_et_aucun_changement():
    wanted = build("role_required")
    changes = plan({}, wanted, set(wanted))
    assert {c["target_id"] for c in changes} == set(wanted)
    assert all(c["action"] == "add" and c["before"] is None for c in changes)
    assert plan(dict(wanted), wanted, set(wanted)) == []


def test_plan_conserve_membre_et_role_tiers():
    membre = Overwrite(500, "member", VIEW, 0)
    tiers = Overwrite(600, "role", 0, TEXT_WRITE)
    current = {500: membre, 600: tiers}
    wanted = build("role_required")
    changes = plan(current, wanted, {EVERYONE, BOT, R1})
    assert 500 not in {c["target_id"] for c in changes}
    assert 600 not in {c["target_id"] for c in changes}


def test_role_requis_vers_public_retire_everyone_et_roles_R():
    ancien = build("role_required", roles=(R1,))
    nouveau = build("public")
    current = {**ancien, 500: Overwrite(500, "member", VIEW, 0)}
    managed = {EVERYONE, BOT, R1}
    changes = plan(current, nouveau, managed)
    removed = {c["target_id"] for c in changes if c["action"] == "remove"}
    assert removed == {EVERYONE, R1}
    assert 500 not in {c["target_id"] for c in changes}
    ev = next(c for c in changes if c["target_id"] == EVERYONE)
    assert ev["after"] is None and ev["before"] == {"allow": 0, "deny": VIEW}
    assert ev["target_type"] == "role"


def test_plan_update():
    current = {EVERYONE: Overwrite(EVERYONE, "role", 0, VIEW)}
    wanted = {EVERYONE: Overwrite(EVERYONE, "role", VIEW, TEXT_WRITE)}
    (c,) = plan(current, wanted, {EVERYONE})
    assert c["action"] == "update"
    assert c["before"] == {"allow": 0, "deny": VIEW}
    assert c["after"] == {"allow": VIEW, "deny": TEXT_WRITE}


def test_plan_ne_retire_pas_hors_managed():
    current = {R1: Overwrite(R1, "role", VIEW, 0)}
    assert plan(current, {}, set()) == []


def test_jeton_stable_et_sensible():
    a = {1: Overwrite(1, "role", 0, VIEW), 2: Overwrite(2, "member", VIEW, 0)}
    b = {2: Overwrite(2, "member", VIEW, 0), 1: Overwrite(1, "role", 0, VIEW)}
    assert preview_token(5, a) == preview_token(5, b)
    assert preview_token(5, a) == preview_token(5, dict(a))
    assert preview_token(5, a) != preview_token(6, a)
    assert preview_token(5, a) != preview_token(5, {**a, 2: Overwrite(2, "member", VIEW, 1)})
    assert preview_token(5, a) != preview_token(5, {1: a[1]})
    assert preview_token(5, {}) != preview_token(5, a)
