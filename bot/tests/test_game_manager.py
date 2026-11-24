"""GameManager (étape 4, tâche 3) : bascule par nom, provisionnement, archivage, commandes
dynamiques regroupées, ping de recherche de joueurs, message de rôles par réaction."""
import asyncio
import os
import re
import sys
from types import SimpleNamespace as N

import discord
import pytest
from discord import app_commands

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cogs.fun import game_manager as gm_module  # noqa: E402
from cogs.system import reaction_roles as rr_module  # noqa: E402
from utils import command_manager, settings  # noqa: E402

GUILD = 42
LEGACY = [  # (clé, nom, couleur, position, émoji) — tels qu'amorcés par la migration 023
    ("dbd", "Dead by Daylight", "#ED4245", 2, "🔪"),
    ("lol", "League of Legends", "#F5A623", 3, "⚔️"),
    ("warframe", "Warframe", "#5865F2", 4, "🚀"),
    ("overwatch", "Overwatch", "#FF9B50", 5, "🌀"),
    ("fortnite", "Fortnite", "#9B59B6", 6, "🏹"),
    ("minecraft", "Minecraft", "#57F287", 7, "⛏️"),
]


def run(coro_fn):
    return asyncio.run(coro_fn())


# ── Faux Discord ─────────────────────────────────────────────────────────────

class FakeRole:
    def __init__(self, id, name, position=1, managed=False, permissions=0):
        self.id, self.name, self.position, self.managed = id, name, position, managed
        self.permissions = discord.Permissions(permissions)
        self.mention = f"<@&{id}>"

    def is_default(self):
        return self.name == "@everyone"

    def __repr__(self):
        return f"Role({self.name})"


class FakeForum:
    def __init__(self, id, name, category=None, topic=None, overwrites=None):
        self.id, self.name, self.category, self.topic = id, name, category, topic
        self.overwrites = dict(overwrites or {})
        self.edits = []
        self.permission_calls = []

    async def edit(self, overwrites, reason=None):
        self.edits.append(overwrites)
        self.overwrites = dict(overwrites)

    async def set_permissions(self, target, overwrite, reason=None):
        self.permission_calls.append((target, overwrite))
        self.overwrites[target] = overwrite


class FakeCategory(discord.CategoryChannel):
    def __init__(self, id):  # noqa: pas d'état Discord
        self.id = id


class FakeGuild:
    def __init__(self, roles=(), forums=(), channels=()):
        self.id = GUILD
        self.roles = list(roles)
        self.forums = list(forums)
        self.channels = list(channels)
        self.default_role = FakeRole(GUILD, "@everyone", position=0)
        self.me = FakeRole(1, "Hermes", position=50)
        self.me.top_role = self.me
        self.created_roles = []
        self.created_forums = []
        self._next = 5000

    def _id(self):
        self._next += 1
        return self._next

    def get_role(self, role_id):
        return next((r for r in self.roles if r.id == role_id), None)

    def get_channel(self, channel_id):
        return next((c for c in [*self.forums, *self.channels] if c.id == channel_id), None)

    async def create_role(self, name, mentionable=False, color=None, reason=None):
        role = FakeRole(self._id(), name)
        role.color = color
        self.roles.append(role)
        self.created_roles.append(role)
        return role

    async def create_forum_channel(self, name, category=None, topic=None, overwrites=None, reason=None):
        forum = FakeForum(self._id(), name, category, topic, overwrites)
        self.forums.append(forum)
        self.created_forums.append(forum)
        return forum


class FakeTree:
    def __init__(self, global_names=()):
        self.global_cmds = {n: N(name=n, description="") for n in global_names}
        self.guild_cmds: dict[int, dict] = {}
        self.syncs = []

    def add_command(self, command, *, guild=None, override=False):
        cmds = self.guild_cmds.setdefault(guild.id, {}) if guild else self.global_cmds
        if command.name in cmds and not override:
            raise app_commands.CommandAlreadyRegistered(command.name, guild.id if guild else None)
        cmds[command.name] = command

    def remove_command(self, name, *, guild=None):
        cmds = self.guild_cmds.get(guild.id, {}) if guild else self.global_cmds
        return cmds.pop(name, None)

    def get_commands(self, *, guild=None):
        return list((self.guild_cmds.get(guild.id, {}) if guild else self.global_cmds).values())

    async def sync(self, *, guild=None):
        self.syncs.append(guild.id if guild else None)

    def copy_global_to(self, *, guild):
        self.guild_cmds.setdefault(guild.id, {}).update(self.global_cmds)

    def guild_names(self):
        return set(self.guild_cmds.get(GUILD, {}))


class FakeBot:
    def __init__(self, guild, tree=None):
        self.guild = guild
        self.tree = tree or FakeTree()
        self.cogs = {}
        self.user = N(id=1, name="Hermes")
        self.channels = {}

    def get_guild(self, _):
        return self.guild

    def get_cog(self, name):
        return self.cogs.get(name)

    def get_channel(self, channel_id):
        return self.channels.get(channel_id)

    async def wait_until_ready(self):
        return None


class FakeDB:
    """``site_games`` en mémoire : SELECT des jeux et UPDATE ... SET col = $n WHERE key = $1."""

    def __init__(self, rows):
        self.rows = {r["key"]: r for r in rows}
        self.updates = []

    async def fetch(self, sql, *args):
        assert "FROM site_games" in sql
        return [dict(r) for r in sorted(self.rows.values(), key=lambda r: (r["position"], r["key"]))]

    async def execute(self, sql, *args):
        m = re.fullmatch(r"UPDATE site_games SET (.+) WHERE key = \$1", sql)
        assert m, sql
        key, values = args[0], args[1:]
        cols = [part.split(" = ")[0] for part in m.group(1).split(", ")]
        assert len(cols) == len(values)
        self.rows[key].update(zip(cols, values))
        self.updates.append((key, dict(zip(cols, values))))


def row(key, name, color="#5865F2", position=1, emoji=None, command=None,
        provisioned=False, archived=False, role_id=None, forum_id=None, cooldown=3600):
    return {"key": key, "name": name, "color": color, "position": position,
            "discord_role_id": role_id, "forum_channel_id": forum_id, "emoji": emoji,
            "command_name": command, "lfg_cooldown": cooldown,
            "provisioned": provisioned, "archived": archived}


def legacy_rows():
    rows = [row(k, n, c, p, e, k, provisioned=True) for k, n, c, p, e in LEGACY]
    rows.append(row("war-dogs", "War Dogs", "#A12D2F", 1))  # non provisionné, sans émoji
    return rows


def legacy_guild():
    roles = [FakeRole(100 + i, n) for i, (_, n, *_rest) in enumerate(LEGACY)]
    forums = [FakeForum(200 + i, k, overwrites={"existant": "intact"}) for i, (k, *_rest) in enumerate(LEGACY)]
    return FakeGuild(roles, forums)


@pytest.fixture
def make(monkeypatch):
    monkeypatch.setenv("GUILD_ID", str(GUILD))
    monkeypatch.setattr(settings, "_cache", {})
    monkeypatch.setattr(gm_module, "SYNC_DELAY", 0.05)
    monkeypatch.setattr(gm_module, "ready", asyncio.Event())
    monkeypatch.setattr(rr_module, "REACTION_DELAY", 0)

    def factory(rows=None, guild=None, tree=None):
        db = FakeDB(legacy_rows() if rows is None else rows)
        monkeypatch.setattr(gm_module, "db_manager", db)
        guild = guild or legacy_guild()
        bot = FakeBot(guild, tree)
        manager = gm_module.GameManager(bot)
        bot.cogs["GameManager"] = manager
        return N(db=db, guild=guild, bot=bot, tree=bot.tree, gm=manager)
    return factory


# ── Bascule au démarrage ─────────────────────────────────────────────────────

def test_demarrage_rattache_par_nom_sans_rien_creer(make):
    async def scenario():
        e = make()
        await e.gm.cog_load()
        return e

    e = run(scenario)
    assert e.guild.created_roles == [] and e.guild.created_forums == []
    for i, (key, *_rest) in enumerate(LEGACY):
        assert e.db.rows[key]["discord_role_id"] == 100 + i
        assert e.db.rows[key]["forum_channel_id"] == 200 + i
    # Surcharges des forums existants jamais réécrites au démarrage.
    for forum in e.guild.forums:
        assert forum.edits == [] and forum.permission_calls == []
        assert forum.overwrites == {"existant": "intact"}
    # Mêmes commandes qu'avant ; War Dogs n'en a pas ; main.on_ready synchronise (pas le cog).
    assert e.tree.guild_names() == {k for k, *_ in LEGACY}
    assert e.tree.global_cmds == {}
    assert e.tree.syncs == []
    assert e.db.rows["war-dogs"]["provisioned"] is False
    assert e.gm.status("war-dogs") == {"role": "missing", "forum": "missing", "command": "none"}
    assert e.gm.status("dbd") == {"role": "ok", "forum": "ok", "command": "ok"}
    assert gm_module.ready.is_set()


def test_demarrage_avec_forum_supprime_a_la_main(make):
    async def scenario():
        guild = legacy_guild()
        guild.forums = [f for f in guild.forums if f.name != "lol"]
        e = make(guild=guild)
        await e.gm.cog_load()
        status_before = e.gm.status("lol")
        await e.gm.cog_load()  # redémarrage : toujours aucune création, aucune erreur
        return e, status_before

    e, status = run(scenario)
    assert status == {"role": "ok", "forum": "missing", "command": "ok"}
    assert e.db.rows["lol"]["forum_channel_id"] is None
    assert e.guild.created_forums == [] and e.guild.created_roles == []


def test_demarrage_garde_les_ids_deja_enregistres(make):
    async def scenario():
        rows = legacy_rows()
        rows[0]["discord_role_id"] = 999  # rôle déjà rattaché (même s'il n'existe plus)
        e = make(rows=rows)
        await e.gm.cog_load()
        return e

    e = run(scenario)
    assert e.db.rows["dbd"]["discord_role_id"] == 999
    assert e.gm.status("dbd")["role"] == "missing"


def test_demarrage_base_en_echec_libere_le_message_de_reactions(make):
    class Broken(FakeDB):
        async def fetch(self, sql, *args):
            raise RuntimeError("base indisponible")

    async def scenario():
        e = make()
        gm_module.db_manager = Broken([])
        await e.gm.cog_load()
        return e

    e = run(scenario)
    assert gm_module.ready.is_set()
    assert e.tree.guild_names() == set()


# ── Provisionnement ──────────────────────────────────────────────────────────

def war_dogs_setup(make, roles=()):
    rows = legacy_rows()
    rows[-1].update(emoji="🐺", command_name="wardogs")
    guild = legacy_guild()
    guild.roles.extend(roles)
    return make(rows=rows, guild=guild)


def test_provision_reutilise_un_role_homonyme_et_cree_le_forum(make):
    async def scenario():
        e = war_dogs_setup(make, roles=[FakeRole(300, "War Dogs")])
        settings._cache.update({"staff_roles": "77", "game_forums_category": "500"})
        staff = FakeRole(77, "Staff")
        e.guild.roles.append(staff)
        e.guild.channels.append(FakeCategory(500))
        await e.gm.cog_load()
        result = await e.gm.provision("war-dogs", reuse_existing=True)
        return e, result, staff

    e, result, staff = run(scenario)
    assert e.guild.created_roles == []
    assert result["role_id"] == 300 and result["created"] == ["forum"]
    assert result["command"] == "wardogs"
    forum = e.guild.created_forums[0]
    assert result["forum_id"] == forum.id and forum.name == "war-dogs"
    assert forum.category.id == 500
    assert "/wardogs" in forum.topic and "🐺" in forum.topic
    ows = forum.overwrites
    assert ows[e.guild.default_role].view_channel is False
    role = e.guild.get_role(300)
    assert ows[role].view_channel is True and ows[role].send_messages_in_threads is True
    assert ows[staff].manage_threads is True
    assert ows[e.guild.me].view_channel is True
    assert {"discord_role_id": 300, "forum_channel_id": forum.id,
            "provisioned": True}.items() <= e.db.rows["war-dogs"].items()
    assert "wardogs" in e.tree.guild_names()
    assert e.gm.status("war-dogs") == {"role": "ok", "forum": "ok", "command": "ok"}


def test_provision_reutilise_le_forum_homonyme_sans_toucher_ses_surcharges(make):
    async def scenario():
        e = war_dogs_setup(make)
        e.guild.forums.append(FakeForum(400, "war-dogs", overwrites={"existant": "intact"}))
        await e.gm.cog_load()
        return e, await e.gm.provision("war-dogs", reuse_existing=True)

    e, result = run(scenario)
    assert result["created"] == ["role"] and result["forum_id"] == 400
    assert e.guild.created_roles[0].name == "War Dogs"
    assert e.guild.get_channel(400).overwrites == {"existant": "intact"}


def test_role_supprime_a_la_main_affiche_a_recreer_puis_un_clic_recree(make):
    async def scenario():
        e = make()
        await e.gm.cog_load()
        e.guild.roles = [r for r in e.guild.roles if r.name != "Warframe"]
        missing = e.gm.status("warframe")
        result = await e.gm.provision("warframe")
        again = await e.gm.provision("warframe")  # second clic : rien à recréer
        return e, missing, result, again

    e, missing, result, again = run(scenario)
    assert missing == {"role": "missing", "forum": "ok", "command": "ok"}
    assert result["created"] == ["role"]
    assert e.db.rows["warframe"]["discord_role_id"] == result["role_id"]
    assert again["created"] == []
    assert e.gm.status("warframe") == {"role": "ok", "forum": "ok", "command": "ok"}


def test_provision_d_un_jeu_inconnu(make):
    async def scenario():
        e = make()
        await e.gm.cog_load()
        await e.gm.provision("inconnu")

    with pytest.raises(KeyError):
        run(scenario)


# ── Synchronisation regroupée ────────────────────────────────────────────────

def test_cinq_provisions_une_seule_synchronisation(make):
    async def scenario():
        rows = [row(f"jeu{i}", f"Jeu {i}", position=i, emoji=e, command=f"jeu{i}")
                for i, e in enumerate("🐺🦊🐻🐼🐨")]
        e = make(rows=rows, guild=FakeGuild())
        await e.gm.cog_load()
        for i in range(5):
            await e.gm.provision(f"jeu{i}")
        assert e.tree.syncs == []  # pas encore : regroupée
        await asyncio.sleep(gm_module.SYNC_DELAY * 3)
        first = list(e.tree.syncs)
        await e.gm.archive("jeu0")  # nouvelle modification après la synchronisation : une autre
        await asyncio.sleep(gm_module.SYNC_DELAY * 3)
        return e, first

    e, first = run(scenario)
    assert first == [GUILD]
    assert e.tree.syncs == [GUILD, GUILD]
    assert e.tree.guild_names() == {"jeu1", "jeu2", "jeu3", "jeu4"}


def test_rien_ne_change_aucune_synchronisation(make):
    async def scenario():
        e = make()
        await e.gm.cog_load()
        await e.gm.reload()
        await e.gm.provision("dbd")  # déjà tout en place
        await asyncio.sleep(gm_module.SYNC_DELAY * 3)
        return e

    assert run(scenario).tree.syncs == []


def test_synchronisation_en_echec_ne_bloque_pas_la_suivante(make):
    async def scenario():
        e = make()
        await e.gm.cog_load()
        calls = []

        async def failing(*, guild=None):
            calls.append(guild.id)
            if len(calls) == 1:
                raise discord.HTTPException(N(status=500, reason="x"), "boom")
        e.tree.sync = failing
        await e.gm.archive("dbd")
        await asyncio.sleep(gm_module.SYNC_DELAY * 3)
        await e.gm.unarchive("dbd")
        await asyncio.sleep(gm_module.SYNC_DELAY * 3)
        return calls

    assert run(scenario) == [GUILD, GUILD]


# ── Archivage ────────────────────────────────────────────────────────────────

def test_archive_retire_la_commande_et_verrouille_le_forum(make):
    async def scenario():
        e = make()
        await e.gm.cog_load()
        status = await e.gm.archive("dbd")
        return e, status

    e, status = run(scenario)
    assert "dbd" not in e.tree.guild_names()
    assert e.db.rows["dbd"]["archived"] is True
    assert status == {"role": "ok", "forum": "ok", "command": "none"}
    forum = e.guild.get_channel(200)
    (target, overwrite), = forum.permission_calls
    assert target.name == "Dead by Daylight"
    assert overwrite.view_channel is False  # forum masqué au rôle du jeu
    # Le rôle est gardé.
    assert e.guild.get_role(100) is not None


def test_unarchive_restaure_commande_et_ecriture(make):
    async def scenario():
        e = make()
        await e.gm.cog_load()
        await e.gm.archive("lol")
        status = await e.gm.unarchive("lol")
        return e, status

    e, status = run(scenario)
    assert "lol" in e.tree.guild_names()
    assert status == {"role": "ok", "forum": "ok", "command": "ok"}
    _, overwrite = e.guild.get_channel(201).permission_calls[-1]
    assert overwrite.send_messages_in_threads is True


def test_reload_suit_un_changement_de_nom_de_commande(make):
    async def scenario():
        e = make()
        await e.gm.cog_load()
        e.db.rows["minecraft"]["command_name"] = "mc"
        e.db.rows["fortnite"]["archived"] = True
        await e.gm.reload()
        return e

    e = run(scenario)
    names = e.tree.guild_names()
    assert "mc" in names and "minecraft" not in names and "fortnite" not in names


def test_resync_permissions_reecrit_tous_les_forums(make):
    async def scenario():
        e = make()
        await e.gm.cog_load()
        await e.gm.archive("overwatch")
        return e, await e.gm.resync_permissions()

    e, result = run(scenario)
    assert result == {"forums": 6, "failed": []}
    for forum in e.guild.forums:
        (ows,) = forum.edits
        assert ows[e.guild.default_role].view_channel is False
        assert e.guild.me in ows
    ow = e.guild.get_channel(203).edits[0][e.guild.get_role(103)]
    assert ow.view_channel is False  # overwatch archivé : masqué


# ── Noms de commande pris ────────────────────────────────────────────────────

def test_nom_deja_pris_par_une_commande_du_bot(make):
    async def scenario():
        rows = legacy_rows()
        rows[0]["command_name"] = "rang"  # collision avec /rang (commande globale copiée sur le serveur)
        tree = FakeTree(global_names=["rang", "blague"])
        tree.copy_global_to(guild=discord.Object(id=GUILD))
        e = make(rows=rows, tree=tree)
        await e.gm.cog_load()
        return e

    e = run(scenario)
    assert e.tree.guild_cmds[GUILD]["rang"].description == ""  # /rang intact
    assert e.gm.status("dbd")["command"] == "missing"
    taken = e.gm.taken_command_names(exclude_key="war-dogs")
    assert {"rang", "blague", "lol", "minecraft"} <= taken
    assert "wardogs" not in taken
    assert "lol" not in e.gm.taken_command_names(exclude_key="lol")


def test_nom_de_commande_globale_refuse_avant_la_copie_sur_le_serveur(make):
    # Ordre réel de main.on_ready : cogs chargés (commandes de jeux) puis copy_global_to.
    async def scenario():
        rows = legacy_rows()
        rows[1]["command_name"] = "blague"
        e = make(rows=rows, tree=FakeTree(global_names=["rang", "blague"]))
        await e.gm.cog_load()
        names_before_copy = e.tree.guild_names()
        e.tree.copy_global_to(guild=discord.Object(id=GUILD))
        return e, names_before_copy

    e, names = run(scenario)
    assert "blague" not in names
    assert e.tree.guild_cmds[GUILD]["blague"].description == ""  # la vraie /blague
    assert e.gm.status("lol")["command"] == "missing"


def test_emojis_pris(make):
    async def scenario():
        e = make()
        await e.gm.cog_load()
        return e

    e = run(scenario)
    assert e.gm.taken_emojis() >= {"⭐", "📺", "🎭", "🔪", "⛏️"}
    assert "🔪" not in e.gm.taken_emojis(exclude_key="dbd")


# ── Ping de recherche de joueurs ─────────────────────────────────────────────

class FakeThread(discord.Thread):
    def __init__(self, parent, name):  # noqa: pas d'état Discord
        self._fake_parent = parent
        self.name = name

    @property
    def parent(self):
        return self._fake_parent


class FakeResponse:
    def __init__(self):
        self.sent = []

    async def send_message(self, content=None, *, embed=None, ephemeral=False, allowed_mentions=None):
        self.sent.append(N(content=content, embed=embed, ephemeral=ephemeral, mentions=allowed_mentions))


def interaction(guild, channel, command_name):
    return N(guild=guild, guild_id=GUILD, channel=channel, user=N(mention="<@5>"),
             command=N(name=command_name), response=FakeResponse())


def test_ping_identique_a_l_ancien_comportement(make, monkeypatch):
    async def enabled(*a, **k):
        return True
    monkeypatch.setattr(command_manager.CommandStatusManager, "get", staticmethod(enabled))

    async def scenario():
        e = make()
        await e.gm.cog_load()
        command = e.tree.guild_cmds[GUILD]["dbd"]
        assert command.description == "Ping les joueurs Dead by Daylight pour une partie"
        thread = FakeThread(e.guild.get_channel(200), "Recherche Joueurs")
        first, second = interaction(e.guild, thread, "dbd"), interaction(e.guild, thread, "dbd")
        await command.callback(first)
        await command.callback(second)
        wrong = interaction(e.guild, FakeThread(e.guild.get_channel(201), "Recherche Joueurs"), "dbd")
        await command.callback(wrong)
        return first, second, wrong

    first, second, wrong = run(scenario)
    (ping,) = first.response.sent
    assert ping.content == "<@&100>" and ping.ephemeral is False
    assert ping.embed.title == "🔪  Recherche de joueurs — Dead by Daylight"
    assert ping.embed.description == "<@5> cherche des joueurs pour une partie !"
    assert ping.embed.color.value == 0xED4245
    assert ping.embed.footer.text.startswith("Prochain ping disponible dans 1h")
    assert ping.mentions.roles is True
    (cool,) = second.response.sent
    assert cool.ephemeral and "a déjà été pingé récemment" in cool.embed.description
    assert "Prochain ping dans **59m" in cool.embed.description
    (refused,) = wrong.response.sent
    assert refused.ephemeral and "Recherche Joueurs" in refused.embed.description


def test_ping_hors_fil_et_role_supprime(make, monkeypatch):
    async def enabled(*a, **k):
        return True
    monkeypatch.setattr(command_manager.CommandStatusManager, "get", staticmethod(enabled))

    async def scenario():
        e = make()
        await e.gm.cog_load()
        command = e.tree.guild_cmds[GUILD]["lol"]
        outside = interaction(e.guild, N(name="général"), "lol")
        await command.callback(outside)
        e.guild.roles = [r for r in e.guild.roles if r.id != 101]
        no_role = interaction(e.guild, FakeThread(e.guild.get_channel(201), "recherche joueurs"), "lol")
        await command.callback(no_role)
        return outside, no_role

    outside, no_role = run(scenario)
    assert outside.response.sent[0].embed.description == "❌ Cette commande est réservée aux forums **League of Legends**."
    assert "Rôle **League of Legends** introuvable" in no_role.response.sent[0].embed.description


def test_commande_desactivee_depuis_le_site(make, monkeypatch):
    asked = []

    async def disabled(name, guild_id=None, use_cache=True):
        asked.append((name, guild_id))
        return False

    async def by(name, guild_id=None):
        return "Admin"
    monkeypatch.setattr(command_manager.CommandStatusManager, "get", staticmethod(disabled))
    monkeypatch.setattr(command_manager.CommandStatusManager, "get_disabled_by", staticmethod(by))

    async def scenario():
        e = make()
        await e.gm.cog_load()
        it = interaction(e.guild, FakeThread(e.guild.get_channel(205), "recherche joueurs"), "minecraft")
        await e.tree.guild_cmds[GUILD]["minecraft"].callback(it)
        return it

    it = run(scenario)
    assert asked == [("minecraft", GUILD)]  # même nom que dans command_manager, par serveur
    (msg,) = it.response.sent
    assert msg.ephemeral and msg.embed.description == "🔒 La commande `/minecraft` a été désactivée par **Admin**."


def test_cooldown_personnalise_dans_le_pied(make, monkeypatch):
    async def enabled(*a, **k):
        return True
    monkeypatch.setattr(command_manager.CommandStatusManager, "get", staticmethod(enabled))

    async def scenario():
        rows = legacy_rows()
        rows[0]["lfg_cooldown"] = 1800
        e = make(rows=rows)
        await e.gm.cog_load()
        it = interaction(e.guild, FakeThread(e.guild.get_channel(200), "recherche joueurs"), "dbd")
        await e.tree.guild_cmds[GUILD]["dbd"].callback(it)
        return it

    assert run(scenario).response.sent[0].embed.footer.text.startswith("Prochain ping disponible dans 30 min")


# ── Message de rôles par réaction ────────────────────────────────────────────

class FakeReaction:
    def __init__(self, emoji, me=True):
        self.emoji, self.me = emoji, me


class FakeMessage:
    def __init__(self, id, author, embed, reactions=()):
        self.id, self.author, self.embeds = id, author, [embed]
        self.reactions = [FakeReaction(e) for e in reactions]
        self.edited, self.added, self.removed = [], [], []

    async def edit(self, embed):
        self.edited.append(embed)
        self.embeds = [embed]

    async def add_reaction(self, emoji):
        self.added.append(emoji)
        self.reactions.append(FakeReaction(emoji))

    async def remove_reaction(self, emoji, member):
        self.removed.append(emoji)
        self.reactions = [r for r in self.reactions if not (r.me and str(r.emoji) == emoji)]


class FakeTextChannel:
    def __init__(self, id, messages=()):
        self.id = id
        self.messages = list(messages)
        self.sent = []

    async def history(self, limit=100):
        for m in self.messages:
            yield m

    async def send(self, embed):
        msg = FakeMessage(900, None, embed)
        self.messages.append(msg)
        self.sent.append(msg)
        return msg


SIX = ["🔪", "⚔️", "🚀", "🌀", "🏹", "⛏️"]
NOTIF = ["⭐", "📺", "🎭"]


def reaction_env(e, messages=()):
    rr = object.__new__(rr_module.ReactionRoles)  # sans démarrer la tâche _setup
    rr.bot, rr.message_id, rr._refresh_lock = e.bot, None, asyncio.Lock()
    rr._unsafe_warned = set()
    channel = FakeTextChannel(800, messages)
    for m in channel.messages:
        m.author = e.bot.user
    rr.channel_id = channel.id
    e.bot.channels[channel.id] = channel
    e.bot.cogs["ReactionRoles"] = rr
    return rr, channel


def game_field(embed):
    return next(f.value for f in embed.fields if f.name == "🎮 Rôles Jeux")


def test_message_de_reactions_avec_les_jeux_actifs_et_les_notifications(make):
    async def scenario():
        e = make()
        await e.gm.cog_load()
        rr, channel = reaction_env(e)
        await rr.refresh()
        return channel

    channel = run(scenario)
    (msg,) = channel.sent
    assert msg.added == NOTIF + SIX  # ordre identique à l'ancien message
    embed = msg.embeds[0]
    assert embed.title == rr_module.EMBED_TITLE
    assert game_field(embed) == "\n".join(f"{e}  **{n}**" for _, n, _, _, e in LEGACY)
    notif = next(f.value for f in embed.fields if f.name == "📢 Notifications")
    assert notif == "⭐  **annonces globales**\n📺  **annonces streams/vidéos**\n🎭  **Annonce Animation**"


def test_message_existant_reutilise_sans_modification_a_la_bascule(make):
    async def scenario():
        e = make()
        await e.gm.cog_load()
        old_embed = rr_module._build_embed(e.gm.reaction_games())
        existing = FakeMessage(700, None, old_embed, reactions=NOTIF + SIX)
        rr, channel = reaction_env(e, [existing])
        await rr.refresh()
        return rr, channel, existing

    rr, channel, existing = run(scenario)
    assert channel.sent == [] and rr.message_id == 700
    assert existing.edited == [] and existing.added == [] and existing.removed == []


def test_jeu_archive_puis_ajoute_message_reconstruit_et_reactions_synchronisees(make):
    async def scenario():
        rows = legacy_rows()
        rows[-1].update(emoji="🐺", command_name="wardogs", position=8)
        guild = legacy_guild()
        e = make(rows=rows, guild=guild)
        await e.gm.cog_load()
        existing = FakeMessage(700, None, rr_module._build_embed(e.gm.reaction_games()),
                               reactions=NOTIF + SIX)
        rr, channel = reaction_env(e, [existing])
        await e.gm.archive("warframe")          # GameManager prévient ReactionRoles
        await e.gm.provision("war-dogs")
        return e, channel, existing

    e, channel, existing = run(scenario)
    assert channel.sent == []                   # même message, modifié
    assert existing.removed == ["🚀"]
    assert existing.added == ["🐺"]
    lines = game_field(existing.embeds[0]).split("\n")
    assert [line.split()[0] for line in lines] == ["🔪", "⚔️", "🌀", "🏹", "⛏️", "🐺"]
    assert "🐺  **War Dogs**" in lines


def test_reaction_donne_le_role_du_jeu_par_identifiant(make):
    async def scenario():
        e = make()
        await e.gm.cog_load()
        rr, _ = reaction_env(e)
        rr.message_id = 700
        member = N(id=5, added=[])

        async def add_roles(role, reason=None):
            member.added.append(role.id)
        member.add_roles = add_roles
        e.guild.get_member = lambda uid: member if uid == 5 else None
        e.guild.get_role(100).name = "DBD renommé"  # le rôle reste celui de site_games
        payload = N(message_id=700, user_id=5, guild_id=GUILD, emoji="🔪")
        await rr.on_raw_reaction_add(payload)
        await rr.on_raw_reaction_add(N(message_id=700, user_id=5, guild_id=GUILD, emoji="🐺"))
        return member

    assert run(scenario).added == [100]


# ── Correction tour 1 : échecs Discord, jeux non chargés, couleur ───────────

def forbidden():
    return discord.Forbidden(N(status=403, reason="Forbidden"), "Missing Permissions")


def test_archive_refuse_par_discord_commande_et_message_restent_coherents(make):
    async def scenario():
        e = make()
        await e.gm.cog_load()
        existing = FakeMessage(700, None, rr_module._build_embed(e.gm.reaction_games()),
                               reactions=NOTIF + SIX)
        reaction_env(e, [existing])

        async def refused(*args, **kwargs):
            raise forbidden()
        e.guild.get_channel(202).set_permissions = refused
        with pytest.raises(discord.Forbidden):
            await e.gm.archive("warframe")
        return e, existing

    e, existing = run(scenario)
    assert e.db.rows["warframe"]["archived"] is True
    assert "warframe" not in e.tree.guild_names()
    assert e.gm.status("warframe")["command"] == "none"
    assert existing.removed == ["🚀"]
    assert "Warframe" not in game_field(existing.embeds[0])


def test_unarchive_refuse_par_discord_commande_reinscrite(make):
    async def scenario():
        e = make()
        await e.gm.cog_load()
        await e.gm.archive("lol")

        async def refused(*args, **kwargs):
            raise forbidden()
        e.guild.get_channel(201).set_permissions = refused
        with pytest.raises(discord.Forbidden):
            await e.gm.unarchive("lol")
        return e

    e = run(scenario)
    assert e.db.rows["lol"]["archived"] is False
    assert "lol" in e.tree.guild_names()
    assert e.gm.status("lol")["command"] == "ok"


def test_provision_refuse_par_discord_commandes_en_accord_avec_la_base(make):
    async def scenario():
        guild = legacy_guild()
        guild.forums = [f for f in guild.forums if f.name != "lol"]
        e = make(guild=guild)
        await e.gm.cog_load()
        e.db.rows["lol"]["command_name"] = "lolx"  # modifié sur le site avant le clic

        async def refused(*args, **kwargs):
            raise forbidden()
        guild.create_forum_channel = refused
        with pytest.raises(discord.Forbidden):
            await e.gm.provision("lol")
        return e

    e = run(scenario)
    names = e.tree.guild_names()
    assert "lolx" in names and "lol" not in names
    assert e.gm.status("lol")["command"] == "ok"


def test_base_en_echec_le_message_de_reactions_garde_ses_jeux(make):
    class Broken(FakeDB):
        async def fetch(self, sql, *args):
            raise RuntimeError("base indisponible")

    async def scenario():
        e = make()
        gm_module.db_manager = Broken([])
        await e.gm.cog_load()
        assert e.gm.loaded is False
        embed = rr_module._build_embed([(em, n, None) for _, n, _, _, em in LEGACY])
        existing = FakeMessage(700, None, embed, reactions=["⭐", "🎭", *SIX])  # 📺 manquante
        rr, _ = reaction_env(e, [existing])
        await rr.refresh()
        return existing

    existing = run(scenario)
    assert existing.edited == [] and existing.removed == []
    assert existing.added == ["📺"]  # seules les notifications peuvent être ajoutées
    assert game_field(existing.embeds[0]).split(chr(10)) == [f"{em}  **{n}**" for _, n, _, _, em in LEGACY]


def test_cog_des_jeux_absent_le_message_de_reactions_garde_ses_jeux(make):
    async def scenario():
        e = make()
        del e.bot.cogs["GameManager"]
        embed = rr_module._build_embed([(em, n, None) for _, n, _, _, em in LEGACY])
        existing = FakeMessage(700, None, embed, reactions=NOTIF + SIX)
        rr, _ = reaction_env(e, [existing])
        await rr.refresh()
        return existing

    existing = run(scenario)
    assert existing.edited == [] and existing.removed == [] and existing.added == []


def test_jeux_charges_au_demarrage(make):
    async def scenario():
        e = make()
        before = e.gm.loaded
        await e.gm.cog_load()
        return before, e.gm.loaded

    assert run(scenario) == (False, True)


def test_role_cree_par_provision_prend_la_couleur_du_jeu(make):
    async def scenario():
        e = war_dogs_setup(make)
        await e.gm.cog_load()
        await e.gm.provision("war-dogs")
        return e

    e = run(scenario)
    (role,) = e.guild.created_roles
    assert role.color == discord.Color(0xA12D2F)


# ── Correction finale C1 : anti-escalade du provisionnement et des réactions ─

@pytest.mark.parametrize("name", ["War Dogs", "war dogs", "  WAR DOGS "])
def test_provision_sans_reutilisation_refuse_un_role_homonyme(make, name):
    async def scenario():
        e = war_dogs_setup(make, roles=[FakeRole(300, name)])
        await e.gm.cog_load()
        with pytest.raises(gm_module.GameRefused) as exc:
            await e.gm.provision("war-dogs")
        return e, exc.value

    e, error = run(scenario)
    assert "un rôle de ce nom existe déjà" in str(error).lower()
    assert e.guild.created_roles == [] and e.guild.created_forums == []
    assert e.db.rows["war-dogs"]["discord_role_id"] is None


def test_provision_sans_reutilisation_refuse_un_forum_homonyme(make):
    async def scenario():
        e = war_dogs_setup(make)
        e.guild.forums.append(FakeForum(400, "War-Dogs"))
        await e.gm.cog_load()
        with pytest.raises(gm_module.GameRefused) as exc:
            await e.gm.provision("war-dogs")
        return e, exc.value

    e, error = run(scenario)
    assert "un forum de ce nom existe déjà" in str(error).lower()
    assert e.guild.created_forums == [] and e.db.rows["war-dogs"]["forum_channel_id"] is None


@pytest.mark.parametrize("role", [
    FakeRole(300, "War Dogs", permissions=discord.Permissions(administrator=True).value),
    FakeRole(300, "War Dogs", permissions=discord.Permissions(manage_roles=True).value),
    FakeRole(300, "War Dogs", managed=True),
    FakeRole(300, "War Dogs", position=60),  # au-dessus du bot
    FakeRole(300, "War Dogs", position=50),  # au niveau du bot
])
@pytest.mark.parametrize("attached", [False, True])
def test_provision_ne_reutilise_jamais_un_role_dangereux(make, role, attached):
    """Même pour un admin (réutilisation permise) et même rattaché par identifiant."""
    async def scenario():
        e = war_dogs_setup(make, roles=[role])
        if attached:
            e.db.rows["war-dogs"]["discord_role_id"] = role.id
        await e.gm.cog_load()
        with pytest.raises(gm_module.GameRefused):
            await e.gm.provision("war-dogs", reuse_existing=True)
        return e

    e = run(scenario)
    assert e.guild.created_roles == [] and e.guild.created_forums == []
    assert e.db.rows["war-dogs"]["provisioned"] is False


def test_provision_ne_reutilise_jamais_everyone(make):
    async def scenario():
        e = war_dogs_setup(make)
        e.db.rows["war-dogs"]["discord_role_id"] = GUILD
        e.guild.roles.append(e.guild.default_role)
        await e.gm.cog_load()
        with pytest.raises(gm_module.GameRefused):
            await e.gm.provision("war-dogs", reuse_existing=True)

    run(scenario)


@pytest.mark.parametrize("by_id", [False, True])
def test_provision_refuse_un_forum_deja_rattache_a_un_autre_jeu(make, by_id):
    async def scenario():
        e = war_dogs_setup(make)
        await e.gm.cog_load()  # lol rattaché au forum 201 « lol »
        if by_id:
            e.db.rows["war-dogs"]["forum_channel_id"] = 201
        else:
            e.guild.forums.append(FakeForum(401, "war-dogs"))
            e.db.rows["lol"]["forum_channel_id"] = 401
        with pytest.raises(gm_module.GameRefused) as exc:
            await e.gm.provision("war-dogs", reuse_existing=True)
        return e, exc.value

    e, error = run(scenario)
    assert "déjà le forum du jeu" in str(error)
    assert e.db.rows["war-dogs"]["provisioned"] is False
    assert e.guild.created_roles == []  # tout est vérifié avant la première création


def test_jeux_historiques_non_affectes(make):
    """Les 6 jeux rattachés par nom au démarrage (rôles sans permissions) : re-provision possible
    sans réutilisation explicite, réactions données."""
    async def scenario():
        e = make()
        await e.gm.cog_load()
        results = [await e.gm.provision(k) for k, *_ in LEGACY]
        rr, _ = reaction_env(e)
        roles = [rr._role_for(e.guild, em) for *_, em in LEGACY]
        return e, results, roles

    e, results, roles = run(scenario)
    assert all(r["created"] == [] for r in results)
    assert [r.id for r in roles] == [100 + i for i in range(len(LEGACY))]
    assert e.guild.created_roles == [] and e.guild.created_forums == []


@pytest.mark.parametrize("kwargs", [
    {"permissions": discord.Permissions(administrator=True).value},
    {"permissions": discord.Permissions(kick_members=True).value},
    {"managed": True},
])
def test_reactions_ne_donnent_jamais_un_role_a_permissions(make, caplog, kwargs):
    async def scenario():
        e = make()
        await e.gm.cog_load()
        bad = FakeRole(100, "Dead by Daylight", **kwargs)
        e.guild.roles[0] = bad
        rr, _ = reaction_env(e)
        rr.message_id = 700
        member = N(id=5, added=[], removed=[])

        async def add_roles(role, reason=None):
            member.added.append(role.id)

        async def remove_roles(role, reason=None):
            member.removed.append(role.id)
        member.add_roles, member.remove_roles = add_roles, remove_roles
        e.guild.get_member = lambda uid: member if uid == 5 else None
        for _ in range(2):
            await rr.on_raw_reaction_add(N(message_id=700, user_id=5, guild_id=GUILD, emoji="🔪"))
        await rr.on_raw_reaction_remove(N(message_id=700, user_id=5, guild_id=GUILD, emoji="🔪"))
        await rr.on_raw_reaction_add(N(message_id=700, user_id=5, guild_id=GUILD, emoji="⚔️"))
        return member

    with caplog.at_level("WARNING"):
        member = run(scenario)
    assert member.added == [101] and member.removed == []
    warnings = [r for r in caplog.records if "Dead by Daylight" in r.getMessage()]
    assert len(warnings) == 1  # averti une seule fois


# ── Correction finale I2 : aperçu détaillé du resync ; T3-1 : resync complet ─

def real_overwrites(guild):
    """Remplace les surcharges fictives des forums historiques par des surcharges Discord."""
    for forum in guild.forums:
        forum.overwrites = {guild.default_role: discord.PermissionOverwrite(view_channel=False)}

def test_apercu_du_resync_liste_les_surcharges_retirees_ou_modifiees(make):
    async def scenario():
        e = make()
        settings._cache.update({"staff_roles": "77"})
        staff, guest, modo = FakeRole(77, "Staff"), FakeRole(78, "Invité"), FakeRole(79, "Modération")
        e.guild.roles.extend([staff, guest, modo])
        await e.gm.cog_load()
        real_overwrites(e.guild)
        lol = e.guild.get_channel(201)
        lol_role = e.guild.get_role(101)
        lol.overwrites = {
            e.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            lol_role: discord.PermissionOverwrite(view_channel=True),   # sera complété
            guest: discord.PermissionOverwrite(view_channel=True),      # sera retiré
            modo: discord.PermissionOverwrite(view_channel=True, manage_threads=True),  # retiré
        }
        before = {f.id: dict(f.overwrites) for f in e.guild.forums}
        return e, await e.gm.resync_preview(), before

    e, preview, before = run(scenario)
    assert [p["key"] for p in preview] == [k for k, *_ in LEGACY]
    # Lecture seule : aucune surcharge écrite.
    assert all(f.edits == [] and f.permission_calls == [] for f in e.guild.forums)
    assert {f.id: f.overwrites for f in e.guild.forums} == before
    lol = next(p for p in preview if p["key"] == "lol")
    assert lol["forum"] == "lol" and lol["forum_id"] == "201" and lol["game"] == "League of Legends"
    changes = {c["target"]: c for c in lol["changes"]}
    assert changes["Invité"] == {"target": "Invité", "kind": "role", "change": "removed",
                                 "before": {"allow": ["view_channel"], "deny": []}, "after": None}
    assert changes["Modération"]["change"] == "removed"
    assert changes["Modération"]["before"]["allow"] == ["manage_threads", "view_channel"]
    modified = changes["League of Legends"]
    assert modified["change"] == "modified"
    assert modified["before"] == {"allow": ["view_channel"], "deny": []}
    assert modified["after"]["allow"] == ["send_messages", "send_messages_in_threads", "view_channel"]
    assert changes["Staff"]["change"] == "added" and changes["Staff"]["before"] is None
    assert changes["Hermes"]["change"] == "added"
    assert "@everyone" not in changes  # déjà conforme : non listé


def test_apercu_ignore_les_jeux_sans_forum(make):
    async def scenario():
        guild = legacy_guild()
        guild.forums = [f for f in guild.forums if f.name != "lol"]
        e = make(guild=guild)
        await e.gm.cog_load()
        real_overwrites(guild)
        return await e.gm.resync_preview()

    keys = [p["key"] for p in run(scenario)]
    assert "lol" not in keys and "war-dogs" not in keys and len(keys) == 5


def test_resync_continue_apres_un_forum_en_echec(make):
    async def scenario():
        e = make()
        await e.gm.cog_load()

        async def refused(*args, **kwargs):
            raise forbidden()
        e.guild.get_channel(201).edit = refused
        return e, await e.gm.resync_permissions()

    e, result = run(scenario)
    assert result["forums"] == 5
    assert result["failed"] == [{"key": "lol", "forum": "lol", "error": "permission refusée"}]
    assert all(len(f.edits) == 1 for f in e.guild.forums if f.id != 201)


def test_resync_tous_en_echec_erreur_relancee(make):
    async def scenario():
        e = make()
        await e.gm.cog_load()

        async def refused(*args, **kwargs):
            raise forbidden()
        for f in e.guild.forums:
            f.edit = refused
        await e.gm.resync_permissions()

    with pytest.raises(discord.Forbidden):
        run(scenario)
