"""Rôles autorisés par commande : cache, contrôle global de l'arbre et ``administration_only`` (étape 6, tâche 2)."""
import asyncio
import os
import pathlib
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import discord  # noqa: E402
import pytest  # noqa: E402
from discord import app_commands  # noqa: E402

from utils import command_permissions as cp  # noqa: E402
from utils.decorators import administration_only  # noqa: E402

ADMIN_ROLE, VIP, MEMBRE, SUPPRIME = 40, 15, 10, 777
OWNER_ID = 999


class FakeRole:
    def __init__(self, rid):
        self.id = rid


class FakeGuild:
    owner_id = OWNER_ID


def member(mid, *role_ids):
    return SimpleNamespace(id=mid, roles=[FakeRole(r) for r in role_ids])


class FakeResponse:
    def __init__(self):
        self.sent = []
        self.done = False

    def is_done(self):
        return self.done

    async def send_message(self, *, embed=None, ephemeral=False, **_):
        self.sent.append((embed, ephemeral))
        self.done = True


def interaction(command, user, *, guild=None, kind=discord.InteractionType.application_command):
    return SimpleNamespace(command=command, user=user, guild=guild or FakeGuild(), type=kind,
                           response=FakeResponse(), followup=None)


class FakeDb:
    def __init__(self, rows=(), fail=False):
        self.rows, self.fail, self.calls = list(rows), fail, 0

    async def fetch(self, query, *args):
        self.calls += 1
        assert "command_permissions" in query
        if self.fail:
            raise ConnectionError("base indisponible")
        return [dict(r) for r in self.rows]


@pytest.fixture
def state(monkeypatch):
    """Cache vierge (comme au démarrage du bot), rôle admin réglé, base simulée."""
    db = FakeDb()
    monkeypatch.setattr(cp, "_allowed", {})
    monkeypatch.setattr(cp, "_loaded", False)
    monkeypatch.setattr(cp, "_last_attempt", float("-inf"))
    monkeypatch.setattr(cp, "_lock", asyncio.Lock())
    monkeypatch.setattr(cp, "db_manager", db)
    monkeypatch.setattr(cp.settings, "get_role",
                        lambda guild, key: FakeRole(ADMIN_ROLE) if key == "admin_role" else None)
    return db


def rows(*pairs):
    return [{"command_name": name, "role_id": rid} for name, rid in pairs]


def make_command(name, *, admin=False):
    async def body(self, interaction):
        interaction.ran = True

    func = administration_only()(body) if admin else body

    async def callback(interaction):
        await func(None, interaction)

    if admin:
        setattr(callback, cp.ADMIN_ONLY_ATTR, True)
    return app_commands.Command(name=name, description="test", callback=callback)


def check(command, user, **kw):
    inter = interaction(command, user, **kw)
    return asyncio.run(cp.check_interaction(inter)), inter


# ── Review Focus 5 : liste relue avant la première commande ─────────────────

def test_premiere_commande_lit_la_liste_sans_rechargement_explicite(state):
    state.rows = rows(("blague", VIP))
    ok, _ = check(make_command("blague"), member(1, MEMBRE))
    assert not ok
    assert state.calls == 1 and cp.is_loaded()
    ok, _ = check(make_command("blague"), member(2, VIP))
    assert ok
    assert state.calls == 1  # cache : pas de nouvelle lecture


def test_on_ready_charge_la_liste_apres_la_base_et_avant_les_cogs():
    source = (pathlib.Path(__file__).resolve().parents[1] / "main.py").read_text(encoding="utf-8")
    on_ready = source[source.index("async def on_ready"):]
    db, load, cogs = (on_ready.index(s) for s in (
        "await init_database()", "await command_permissions.reload()", "await load_cogs()"))
    assert db < load < cogs
    assert "tree_cls=command_permissions.HermesCommandTree" in source


# ── Review Focus 3 : liste vidée = commande rouverte ────────────────────────

def test_liste_videe_rouvre_la_commande_non_admin(state):
    state.rows = rows(("blague", VIP))
    asyncio.run(cp.reload())
    assert not check(make_command("blague"), member(1, MEMBRE))[0]
    state.rows = []
    assert asyncio.run(cp.reload()) == 0
    assert check(make_command("blague"), member(1, MEMBRE))[0]
    assert check(make_command("blague"), member(1))[0]


# ── Review Focus 4 : rôle supprimé encore en base ───────────────────────────

def test_role_supprime_ignore_sans_erreur(state):
    state.rows = rows(("blague", SUPPRIME), ("blague", VIP))
    assert asyncio.run(cp.reload()) == 1
    assert check(make_command("blague"), member(1, VIP))[0]
    assert not check(make_command("blague"), member(2, MEMBRE))[0]


def test_liste_ne_contenant_qu_un_role_supprime_reste_restreinte(state):
    state.rows = rows(("blague", SUPPRIME))
    asyncio.run(cp.reload())
    assert not check(make_command("blague"), member(1, MEMBRE))[0]
    assert check(make_command("blague"), member(2, ADMIN_ROLE))[0]


# ── Règle d'accès appliquée par l'arbre ──────────────────────────────────────

def test_liste_vide_commande_ouverte_a_tous(state):
    assert check(make_command("blague"), member(1))[0]


def test_proprietaire_et_admin_toujours_autorises(state):
    state.rows = rows(("blague", VIP), ("audit", VIP))
    asyncio.run(cp.reload())
    for cmd in (make_command("blague"), make_command("audit", admin=True)):
        assert check(cmd, member(OWNER_ID))[0]
        assert check(cmd, member(5, ADMIN_ROLE))[0]


def test_commande_admin_liste_vide_reservee_au_role_admin(state):
    asyncio.run(cp.reload())
    assert not check(make_command("audit", admin=True), member(1, VIP))[0]
    assert check(make_command("audit", admin=True), member(2, ADMIN_ROLE))[0]


def test_commande_admin_ouverte_a_un_role_de_sa_liste(state):
    state.rows = rows(("audit", VIP))
    asyncio.run(cp.reload())
    assert check(make_command("audit", admin=True), member(1, VIP))[0]
    assert not check(make_command("audit", admin=True), member(2, MEMBRE))[0]


def test_sous_commande_rangee_sous_sa_commande_racine(state):
    group = app_commands.Group(name="ticket", description="Tickets")

    @group.command(name="close", description="Fermer")
    async def close(interaction):
        pass

    state.rows = rows(("ticket", VIP))
    asyncio.run(cp.reload())
    sub = group.get_command("close")
    assert cp.command_key(sub) == "ticket"
    assert not check(sub, member(1, MEMBRE))[0]
    assert check(sub, member(2, VIP))[0]


def test_hors_serveur_seule_une_commande_libre_passe(state):
    state.rows = rows(("audit", VIP))
    asyncio.run(cp.reload())
    user = SimpleNamespace(id=1)  # discord.User : pas de rôles
    assert cp.member_allowed(None, user, "blague", admin_only=False)
    assert not cp.member_allowed(None, user, "audit", admin_only=False)
    assert not cp.member_allowed(None, user, "kick", admin_only=True)


# ── Refus éphémère, sans nommer les rôles ────────────────────────────────────

def test_refus_ephemere_en_francais_sans_role(state):
    state.rows = rows(("blague", VIP))
    ok, inter = check(make_command("blague"), member(1, MEMBRE))
    assert not ok
    [(embed, ephemeral)] = inter.response.sent
    assert ephemeral is True
    assert embed.description == cp.DENIED
    assert "VIP" not in embed.description and str(VIP) not in embed.description


def test_autocompletion_refusee_sans_message(state):
    state.rows = rows(("blague", VIP))
    ok, inter = check(make_command("blague"), member(1, MEMBRE),
                      kind=discord.InteractionType.autocomplete)
    assert not ok and inter.response.sent == []


def test_arbre_du_bot_delegue_au_controle(state):
    state.rows = rows(("blague", VIP))
    tree = object.__new__(cp.HermesCommandTree)
    inter = interaction(make_command("blague"), member(1, MEMBRE))
    assert asyncio.run(tree.interaction_check(inter)) is False
    assert inter.response.sent


# ── administration_only (2e barrière des commandes admin) ────────────────────

def run_admin(user, guild=None):
    @administration_only()
    async def cmd(self, interaction):
        interaction.ran = True

    inter = interaction(SimpleNamespace(name="audit", root_parent=None), user, guild=guild)
    inter.ran = False
    asyncio.run(cmd(None, inter))
    return inter


def test_administration_only_marque_la_commande():
    @administration_only()
    async def cmd(self, interaction):
        pass

    assert getattr(cmd, cp.ADMIN_ONLY_ATTR) is True


def test_administration_only_ouvert_par_la_liste(state):
    state.rows = rows(("audit", VIP))
    asyncio.run(cp.reload())
    assert run_admin(member(1, VIP)).ran
    refused = run_admin(member(2, MEMBRE))
    assert not refused.ran
    [(embed, ephemeral)] = refused.response.sent
    assert ephemeral and embed.description == cp.DENIED


def test_administration_only_liste_vide_role_admin_seul(state):
    asyncio.run(cp.reload())
    assert run_admin(member(1, ADMIN_ROLE)).ran
    assert run_admin(member(OWNER_ID)).ran
    assert not run_admin(member(2, VIP)).ran


def test_commandes_admin_reelles_marquees():
    """Le marqueur traverse ``command_enabled`` (functools.wraps) : commandes des cogs réels."""
    from cogs.moderation.audit import AuditCog as Audit
    from cogs.moderation.kick import KickCog as Kick
    from cogs.system.command_management import CommandManagementCog as CommandManagement
    from cogs.fun.blague import BlagueCog as Blague

    assert cp.is_admin_only(Kick.kick)
    assert cp.is_admin_only(Audit.audit)
    assert cp.is_admin_only(CommandManagement.disable_command)
    assert not cp.is_admin_only(Blague.blague)


def test_commande_de_jeu_dynamique_soumise_a_la_liste(state):
    from cogs.fun.game_manager import Game, GameManager

    game = Game(key="lol", name="LoL", color=0, position=0, role_id=None, forum_id=None, emoji=None,
                command_name="lol", cooldown=60, provisioned=True, archived=False)
    cmd = GameManager(SimpleNamespace())._make_command(game)
    state.rows = rows(("lol", VIP))
    assert not check(cmd, member(1, MEMBRE))[0]
    assert check(cmd, member(2, VIP))[0]


# ── Échecs de lecture ────────────────────────────────────────────────────────

def test_relecture_en_echec_garde_la_liste_connue(state):
    state.rows = rows(("blague", VIP))
    asyncio.run(cp.reload())
    state.fail = True
    with pytest.raises(ConnectionError):
        asyncio.run(cp.reload())
    assert not check(make_command("blague"), member(1, MEMBRE))[0]


def test_jamais_chargee_comportement_d_avant_et_avertissement(state, caplog):
    state.fail = True
    with caplog.at_level("WARNING"):
        assert check(make_command("blague"), member(1, MEMBRE))[0]
    assert "illisibles" in caplog.text
    assert not cp.is_loaded()
    assert not check(make_command("audit", admin=True), member(1, VIP))[0]
    assert check(make_command("audit", admin=True), member(2, ADMIN_ROLE))[0]
    assert state.calls == 1  # nouvel essai au plus toutes les RETRY_S secondes
