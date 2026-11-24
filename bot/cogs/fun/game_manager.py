"""Jeux pilotés par ``site_games`` : rôle, forum réservé et commande ``/<jeu>`` gérés par le bot.

- Au démarrage : lecture de ``site_games`` ; les jeux ``provisioned`` sans identifiant sont
  rattachés par nom (rôle = nom du jeu, forum = ``utils.games.forum_name``), sans rien créer
  ni réécrire les surcharges des forums existants.
- Une commande de serveur par jeu actif (provisionné, non archivé, nom de commande renseigné),
  ajoutée ou retirée de ``bot.tree`` ; synchronisation regroupée (une au plus par ``SYNC_DELAY``).
- ``provision`` / ``archive`` / ``unarchive`` / ``resync_permissions`` : actions déclenchées par
  un admin depuis le site (API interne du bot).
"""
import asyncio
import logging
import os
import time
from dataclasses import dataclass

import discord
from discord import app_commands
from discord.ext import commands

from utils import settings
from utils.command_manager import command_enabled
from utils.database import db_manager
from utils.embed_style import Colors, hermes_embed
from utils.games import DEFAULT_LFG_COOLDOWN, forum_name, forum_overwrites

logger = logging.getLogger(__name__)

# Délai de regroupement des synchronisations de commandes (secondes).
SYNC_DELAY = 60

LFG_THREAD_NAME = "recherche joueurs"

# Posé une fois les jeux lus au démarrage (réussi ou non) : le message de rôles par réaction l'attend.
ready = asyncio.Event()

_COLUMNS = ("key, name, color, position, discord_role_id, forum_channel_id, emoji, "
            "command_name, lfg_cooldown, provisioned, archived")
_WRITABLE = {"discord_role_id", "forum_channel_id", "provisioned", "archived"}


def _color(value) -> int:
    try:
        return int(str(value).lstrip("#"), 16)
    except (TypeError, ValueError):
        return Colors.BLUE


def _duration(seconds: int) -> str:
    """« 1h », « 30 min », « 45 s » (texte du pied de l'annonce)."""
    if seconds and seconds % 3600 == 0:
        return f"{seconds // 3600}h"
    if seconds and seconds % 60 == 0:
        return f"{seconds // 60} min"
    return f"{seconds} s"


@dataclass
class Game:
    key: str
    name: str
    color: int
    position: int
    role_id: int | None
    forum_id: int | None
    emoji: str | None
    command_name: str | None
    cooldown: int
    provisioned: bool
    archived: bool

    @classmethod
    def from_row(cls, row) -> "Game":
        return cls(
            key=row["key"], name=row["name"], color=_color(row["color"]),
            position=row["position"] or 0,
            role_id=row["discord_role_id"], forum_id=row["forum_channel_id"],
            emoji=row["emoji"] or None, command_name=row["command_name"] or None,
            cooldown=row["lfg_cooldown"] or DEFAULT_LFG_COOLDOWN,
            provisioned=bool(row["provisioned"]), archived=bool(row["archived"]),
        )

    @property
    def has_command(self) -> bool:
        return self.provisioned and not self.archived and bool(self.command_name)


class GameManager(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.games: dict[str, Game] = {}
        # clé du jeu -> (nom de commande, nom du jeu) inscrits dans l'arbre
        self._registered: dict[str, tuple[str, str]] = {}
        self._cooldowns: dict[str, float] = {}  # clé -> instant du dernier ping (monotonic)
        self._lock = asyncio.Lock()
        self._sync_task: asyncio.Task | None = None

    # ── Cycle de vie ─────────────────────────────────────────────────────────

    async def cog_load(self):
        # Chargé par main.on_ready après la base et les réglages ; main synchronise l'arbre
        # juste après le chargement des cogs : aucune synchronisation ici.
        try:
            await self._startup()
        except Exception:
            logger.exception("GameManager : démarrage en échec")
        finally:
            ready.set()

    async def cog_unload(self):
        if self._sync_task:
            self._sync_task.cancel()
        for name, _ in self._registered.values():
            self.bot.tree.remove_command(name, guild=self._guild_obj())
        self._registered.clear()

    async def _startup(self):
        async with self._lock:
            await self._load()
            guild = self._guild()
            if guild:
                await self._attach_by_name(guild)
            else:
                logger.warning("GameManager : serveur introuvable, rattachement des jeux ignoré")
            self._reconcile_commands()

    async def _attach_by_name(self, guild: discord.Guild):
        """Bascule : rattache par nom les rôles et forums des jeux provisionnés sans identifiant."""
        for game in self.games.values():
            if not game.provisioned:
                continue
            fields = {}
            if game.role_id is None:
                role = discord.utils.get(guild.roles, name=game.name)
                if role:
                    fields["discord_role_id"] = game.role_id = role.id
                else:
                    logger.warning("Jeu %s : aucun rôle « %s » à rattacher", game.key, game.name)
            if game.forum_id is None:
                forum = discord.utils.get(guild.forums, name=forum_name(game.key))
                if forum:
                    fields["forum_channel_id"] = game.forum_id = forum.id
                else:
                    logger.warning("Jeu %s : aucun forum « %s » à rattacher", game.key, forum_name(game.key))
            if fields:
                await self._save(game.key, **fields)
                logger.info("Jeu %s rattaché par nom : %s", game.key, fields)

    # ── Données ──────────────────────────────────────────────────────────────

    async def _load(self):
        rows = await db_manager.fetch(f"SELECT {_COLUMNS} FROM site_games ORDER BY position, key")
        self.games = {row["key"]: Game.from_row(row) for row in rows}

    async def _save(self, key: str, **fields):
        assert fields and set(fields) <= _WRITABLE, fields
        columns = list(fields)
        sets = ", ".join(f"{c} = ${i + 2}" for i, c in enumerate(columns))
        await db_manager.execute(
            f"UPDATE site_games SET {sets} WHERE key = $1", key, *(fields[c] for c in columns))

    def _game(self, key: str) -> Game:
        game = self.games.get(key)
        if game is None:
            raise KeyError(f"Jeu inconnu : {key}")
        return game

    def _guild(self) -> discord.Guild | None:
        return self.bot.get_guild(int(os.getenv("GUILD_ID", "0")))

    @staticmethod
    def _guild_obj() -> discord.Object:
        return discord.Object(id=int(os.getenv("GUILD_ID", "0")))

    @staticmethod
    def _forum(guild: discord.Guild, forum_id: int | None):
        if not forum_id:
            return None
        return next((f for f in guild.forums if f.id == forum_id), None)

    @staticmethod
    def _role(guild: discord.Guild, role_id: int | None):
        return guild.get_role(role_id) if role_id else None

    # ── API publique (appelée par l'API interne du bot) ──────────────────────

    async def reload(self) -> None:
        """Relit ``site_games`` et met les commandes en accord (après une modification sur le site)."""
        async with self._lock:
            await self._load()
            if self._reconcile_commands():
                self._schedule_sync()
        await self._notify_reaction_roles()

    async def provision(self, key: str) -> dict:
        """Rôle, forum et commande du jeu : réutilisés s'ils existent, créés sinon."""
        async with self._lock:
            await self._load()
            game = self._game(key)
            guild = self._guild()
            if guild is None:
                raise RuntimeError("Serveur Discord introuvable")
            created: list[str] = []

            role = self._role(guild, game.role_id) or discord.utils.get(guild.roles, name=game.name)
            if role is None:
                role = await guild.create_role(
                    name=game.name, mentionable=False,  # seul le bot pingue (allowed_mentions)
                    reason="Rôle de jeu créé depuis le site",
                )
                created.append("role")
            if role.id != game.role_id:
                # Écrit tout de suite : un échec du forum ne fera pas recréer le rôle.
                await self._save(key, discord_role_id=role.id)
                game.role_id = role.id

            forum = self._forum(guild, game.forum_id) or discord.utils.get(guild.forums, name=forum_name(key))
            if forum is None:
                command = f"/{game.command_name}" if game.command_name else "la commande du jeu"
                forum = await guild.create_forum_channel(
                    name=forum_name(key),
                    category=self._category(guild),
                    topic=(f"{game.emoji or '🎮'} Forum {game.name} — Recherche de joueurs. "
                           f"Utilisez {command} pour notifier les joueurs {game.name}."),
                    overwrites=forum_overwrites(
                        guild.default_role, role, settings.get_roles(guild, "staff_roles"),
                        guild.me, game.archived),
                    reason="Forum de jeu créé depuis le site",
                )
                created.append("forum")
            game.forum_id, game.provisioned = forum.id, True
            await self._save(key, forum_channel_id=forum.id, provisioned=True)

            if self._reconcile_commands():
                self._schedule_sync()
        await self._notify_reaction_roles()
        return {
            "role_id": role.id,
            "forum_id": forum.id,
            "command": game.command_name if game.has_command else None,
            "created": created,
        }

    async def archive(self, key: str) -> dict:
        """Retire la commande et verrouille le forum pour le rôle du jeu ; le rôle est gardé."""
        return await self._set_archived(key, True)

    async def unarchive(self, key: str) -> dict:
        return await self._set_archived(key, False)

    async def _set_archived(self, key: str, archived: bool) -> dict:
        async with self._lock:
            await self._load()
            game = self._game(key)
            await self._save(key, archived=archived)
            game.archived = archived
            guild = self._guild()
            if guild:
                forum, role = self._forum(guild, game.forum_id), self._role(guild, game.role_id)
                if forum and role:
                    overwrite = forum_overwrites(guild.default_role, role, [], None, archived)[role]
                    await forum.set_permissions(role, overwrite=overwrite,
                                                reason="Jeu archivé" if archived else "Jeu réactivé")
            if self._reconcile_commands():
                self._schedule_sync()
        await self._notify_reaction_roles()
        return self.status(key)

    async def resync_permissions(self) -> int:
        """Réécrit les surcharges de tous les forums de jeux ; renvoie le nombre de forums traités."""
        async with self._lock:
            await self._load()
            guild = self._guild()
            if guild is None:
                raise RuntimeError("Serveur Discord introuvable")
            staff = settings.get_roles(guild, "staff_roles")
            count = 0
            for game in self.games.values():
                forum = self._forum(guild, game.forum_id) if game.provisioned else None
                if forum is None:
                    continue
                await forum.edit(
                    overwrites=forum_overwrites(guild.default_role, self._role(guild, game.role_id),
                                                staff, guild.me, game.archived),
                    reason="Permissions des forums de jeux resynchronisées",
                )
                count += 1
            return count

    def status(self, key: str) -> dict:
        """``{"role", "forum", "command"}`` : ``ok`` / ``missing`` (``none`` : pas de commande attendue)."""
        game = self._game(key)
        guild = self._guild()
        role_ok = bool(guild and self._role(guild, game.role_id))
        forum_ok = bool(guild and self._forum(guild, game.forum_id))
        if not game.has_command:
            command = "none"
        else:
            registered = self._registered.get(key, (None,))[0] == game.command_name
            command = "ok" if registered else "missing"
        return {"role": "ok" if role_ok else "missing",
                "forum": "ok" if forum_ok else "missing",
                "command": command}

    def statuses(self) -> dict[str, dict]:
        return {key: self.status(key) for key in self.games}

    def taken_command_names(self, exclude_key: str | None = None) -> set[str]:
        """Noms interdits pour le jeu ``exclude_key`` : autres jeux et autres commandes du bot."""
        tree = self.bot.tree
        names = {c.name for c in tree.get_commands()}
        names |= {c.name for c in tree.get_commands(guild=self._guild_obj())}
        names -= {name for name, _ in self._registered.values()}
        names |= {g.command_name for g in self.games.values() if g.command_name and g.key != exclude_key}
        return names

    def taken_emojis(self, exclude_key: str | None = None) -> set[str]:
        """Émojis interdits pour le jeu ``exclude_key`` : autres jeux et rôles de notification."""
        from cogs.system.reaction_roles import NOTIFICATION_ROLES
        return set(NOTIFICATION_ROLES) | {
            g.emoji for g in self.games.values() if g.emoji and g.key != exclude_key}

    def reaction_games(self) -> list[tuple[str, str, int | None]]:
        """``(émoji, nom, id du rôle)`` des jeux actifs, dans l'ordre du site."""
        return [(g.emoji, g.name, g.role_id)
                for g in sorted(self.games.values(), key=lambda g: (g.position, g.key))
                if g.provisioned and not g.archived and g.emoji]

    def game_roles(self) -> dict[str, str]:
        """Clé -> nom du rôle des jeux actifs (joueurs par jeu de la caserne en direct)."""
        guild = self._guild()
        result = {}
        for g in self.games.values():
            if g.provisioned and not g.archived:
                role = self._role(guild, g.role_id) if guild else None
                result[g.key] = role.name if role else g.name
        return result

    # ── Commandes dynamiques ─────────────────────────────────────────────────

    def _reconcile_commands(self) -> bool:
        """Met l'arbre en accord avec les jeux actifs ; ``True`` si quelque chose a changé."""
        guild = self._guild_obj()
        desired = {g.key: (g.command_name, g.name) for g in self.games.values() if g.has_command}
        changed = False
        for key, entry in list(self._registered.items()):
            if desired.get(key) != entry:
                self.bot.tree.remove_command(entry[0], guild=guild)
                del self._registered[key]
                changed = True
        # Commandes globales : main.on_ready les copie sur le serveur après le chargement des cogs
        # (copy_global_to), ce qui écraserait sans bruit une commande de jeu du même nom.
        global_names = {c.name for c in self.bot.tree.get_commands()}
        for key, entry in desired.items():
            if key in self._registered:
                continue
            if entry[0] in global_names:
                logger.error("Commande /%s du jeu %s non enregistrée : nom d'une commande du bot",
                             entry[0], key)
                continue
            try:
                self.bot.tree.add_command(self._make_command(self.games[key]), guild=guild)
            except app_commands.AppCommandError as e:
                # Nom déjà pris par une autre commande, ou limite de 100 atteinte : signalé, pas bloquant.
                logger.error("Commande /%s du jeu %s non enregistrée : %s", entry[0], key, e)
                continue
            self._registered[key] = entry
            changed = True
        return changed

    def _make_command(self, game: Game) -> app_commands.Command:
        key = game.key

        async def callback(interaction: discord.Interaction):
            await self._guarded_ping(interaction, key)

        return app_commands.Command(
            name=game.command_name,
            description=f"Ping les joueurs {game.name} pour une partie"[:100],
            callback=callback,
        )

    def _schedule_sync(self):
        """Une synchronisation dans ``SYNC_DELAY`` s, partagée par toutes les modifications d'ici là."""
        if self._sync_task is None:
            self._sync_task = asyncio.create_task(self._sync_later())

    async def _sync_later(self):
        await asyncio.sleep(SYNC_DELAY)
        self._sync_task = None  # une modification pendant la synchronisation en planifie une autre
        try:
            await self.bot.tree.sync(guild=self._guild_obj())
            logger.info("Commandes de jeux synchronisées")
        except Exception:
            logger.exception("Synchronisation des commandes de jeux en échec")

    def _category(self, guild: discord.Guild):
        category_id = settings.get_int("game_forums_category")
        category = guild.get_channel(category_id) if category_id else None
        return category if isinstance(category, discord.CategoryChannel) else None

    async def _notify_reaction_roles(self):
        cog = self.bot.get_cog("ReactionRoles")
        if cog is None:
            return
        try:
            await cog.refresh()
        except Exception:
            logger.exception("Mise à jour du message de rôles par réaction en échec")

    # ── Ping de recherche de joueurs ─────────────────────────────────────────

    @command_enabled(guild_specific=True)
    async def _guarded_ping(self, interaction: discord.Interaction, key: str):
        await self.lfg_ping(interaction, key)

    def _cooldown_remaining(self, game: Game) -> int:
        """Secondes restantes avant le prochain ping, 0 si disponible."""
        last = self._cooldowns.get(game.key)
        if last is None:
            return 0
        return max(0, int(game.cooldown - (time.monotonic() - last)))

    async def lfg_ping(self, interaction: discord.Interaction, key: str):
        game = self.games.get(key)
        if game is None:
            await interaction.response.send_message(
                embed=hermes_embed(description="❌ Ce jeu n'existe plus.", color=Colors.RED),
                ephemeral=True,
            )
            return

        # Vérification : doit être dans un thread d'un forum
        if not isinstance(interaction.channel, discord.Thread):
            await interaction.response.send_message(
                embed=hermes_embed(
                    description=f"❌ Cette commande est réservée aux forums **{game.name}**.",
                    color=Colors.RED,
                ),
                ephemeral=True,
            )
            return

        # Vérification : bon forum + bon topic
        parent = interaction.channel.parent
        in_right_forum = game.forum_id and parent and parent.id == game.forum_id
        in_lfg_thread = interaction.channel.name.lower() == LFG_THREAD_NAME

        if not in_right_forum or not in_lfg_thread:
            await interaction.response.send_message(
                embed=hermes_embed(
                    description=(
                        f"❌ Cette commande est réservée au topic **Recherche Joueurs** "
                        f"dans le forum **{game.name}**."
                    ),
                    color=Colors.RED,
                ),
                ephemeral=True,
            )
            return

        # Vérification cooldown
        remaining = self._cooldown_remaining(game)
        if remaining > 0:
            minutes, seconds = divmod(remaining, 60)
            await interaction.response.send_message(
                embed=hermes_embed(
                    description=f"⏳ Le rôle **{game.name}** a déjà été pingé récemment.\nProchain ping dans **{minutes}m {seconds}s**.",
                    color=Colors.ORANGE,
                ),
                ephemeral=True,
            )
            return

        # Récupération du rôle
        role = self._role(interaction.guild, game.role_id)
        if not role:
            await interaction.response.send_message(
                embed=hermes_embed(
                    description=f"❌ Rôle **{game.name}** introuvable. Contacte un administrateur.",
                    color=Colors.RED,
                ),
                ephemeral=True,
            )
            return

        # Ping
        self._cooldowns[key] = time.monotonic()
        embed = hermes_embed(
            title=f"{game.emoji or '🎮'}  Recherche de joueurs — {game.name}",
            description=f"{interaction.user.mention} cherche des joueurs pour une partie !",
            color=game.color,
            footer_extra=f"Prochain ping disponible dans {_duration(game.cooldown)}",
        )
        await interaction.response.send_message(
            content=role.mention,
            embed=embed,
            allowed_mentions=discord.AllowedMentions(roles=True),
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(GameManager(bot))
