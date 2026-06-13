"""Commandes LFG (Looking for Group) pour les forums jeux — cooldown 1h par forum."""
import asyncio
import logging
import os
from datetime import datetime, timedelta

import discord
from discord import app_commands
from discord.ext import commands, tasks

from utils.command_manager import command_enabled
from utils.embed_style import Colors, hermes_embed

logger = logging.getLogger(__name__)

GUILD_ID = int(os.getenv('GUILD_ID', '0'))
GAME_FORUMS_CATEGORY_ID = int(os.getenv('GAME_FORUMS_CATEGORY_ID', '0') or '0') or None

COOLDOWN_SECONDS = 3600  # 1 heure

GAMES: dict[str, dict] = {
    "dbd": {
        "name": "Dead by Daylight",
        "role_name": "Dead by Daylight",
        "emoji": "🔪",
        "forum_name": "dbd",
        "color": Colors.RED,
    },
    "lol": {
        "name": "League of Legends",
        "role_name": "League of Legends",
        "emoji": "⚔️",
        "forum_name": "lol",
        "color": Colors.GOLD,
    },
    "warframe": {
        "name": "Warframe",
        "role_name": "Warframe",
        "emoji": "🚀",
        "forum_name": "warframe",
        "color": Colors.BLUE,
    },
    "overwatch": {
        "name": "Overwatch",
        "role_name": "Overwatch",
        "emoji": "🌀",
        "forum_name": "overwatch",
        "color": Colors.ORANGE,
    },
    "fortnite": {
        "name": "Fortnite",
        "role_name": "Fortnite",
        "emoji": "🏹",
        "forum_name": "fortnite",
        "color": Colors.PURPLE,
    },
    "minecraft": {
        "name": "Minecraft",
        "role_name": "Minecraft",
        "emoji": "⛏️",
        "forum_name": "minecraft",
        "color": Colors.GREEN,
    },
}


class GameLFG(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # game_key -> datetime du dernier ping
        self._cooldowns: dict[str, datetime] = {}
        # game_key -> forum channel ID
        self._forum_ids: dict[str, int] = {}
        self._setup.start()

    def cog_unload(self):
        self._setup.cancel()

    @tasks.loop(count=1)
    async def _setup(self):
        await self.bot.wait_until_ready()
        guild = self.bot.get_guild(GUILD_ID)
        if not guild:
            logger.warning("GameLFG: guild introuvable")
            return

        await self._ensure_game_roles(guild)
        await self._ensure_game_forums(guild)

    async def _ensure_game_roles(self, guild: discord.Guild):
        for key, game in GAMES.items():
            role_name = game["role_name"]
            if not discord.utils.get(guild.roles, name=role_name):
                try:
                    await guild.create_role(
                        name=role_name,
                        mentionable=False,  # seul le bot peut ping via allowed_mentions
                        reason="Rôle jeu créé automatiquement par Hermes",
                    )
                    logger.info(f"Rôle jeu créé : '{role_name}'")
                    await asyncio.sleep(0.3)
                except discord.Forbidden:
                    logger.warning(f"Permission refusée pour créer le rôle '{role_name}'")
                except discord.HTTPException as e:
                    logger.error(f"Erreur création rôle '{role_name}': {e}")

    async def _ensure_game_forums(self, guild: discord.Guild):
        category: discord.CategoryChannel | None = None
        if GAME_FORUMS_CATEGORY_ID:
            category = guild.get_channel(GAME_FORUMS_CATEGORY_ID)
            if not isinstance(category, discord.CategoryChannel):
                category = None

        everyone = guild.default_role

        for key, game in GAMES.items():
            forum_name = game["forum_name"]
            existing = discord.utils.get(guild.forums, name=forum_name)
            if existing:
                self._forum_ids[key] = existing.id
                logger.info(f"Forum trouvé : '{forum_name}' ({existing.id})")
                continue

            game_role = discord.utils.get(guild.roles, name=game["role_name"])

            overwrites: dict = {
                everyone: discord.PermissionOverwrite(view_channel=False),
            }
            if game_role:
                overwrites[game_role] = discord.PermissionOverwrite(view_channel=True)

            try:
                forum = await guild.create_forum_channel(
                    name=forum_name,
                    category=category,
                    topic=(
                        f"{game['emoji']} Forum {game['name']} — Recherche de joueurs. "
                        f"Utilisez /{key} pour notifier les joueurs {game['name']}."
                    ),
                    overwrites=overwrites,
                    reason="Forum jeu créé automatiquement par Hermes",
                )
                self._forum_ids[key] = forum.id
                logger.info(f"Forum créé : '{forum_name}' ({forum.id})")
                await asyncio.sleep(0.5)
            except discord.Forbidden:
                logger.warning(f"Permission refusée pour créer le forum '{forum_name}'")
            except discord.HTTPException as e:
                logger.error(f"Erreur création forum '{forum_name}': {e}")

    def _cooldown_remaining(self, key: str) -> int:
        """Retourne le nombre de secondes restantes, 0 si disponible."""
        last = self._cooldowns.get(key)
        if not last:
            return 0
        elapsed = (datetime.utcnow() - last).total_seconds()
        remaining = COOLDOWN_SECONDS - elapsed
        return max(0, int(remaining))

    async def _lfg_ping(self, interaction: discord.Interaction, key: str):
        game = GAMES[key]

        # Vérification : doit être dans un thread d'un forum
        if not isinstance(interaction.channel, discord.Thread):
            await interaction.response.send_message(
                embed=hermes_embed(
                    description=f"❌ Cette commande est réservée aux forums **{game['name']}**.",
                    color=Colors.RED,
                ),
                ephemeral=True,
            )
            return

        # Vérification : bon forum + bon topic
        parent = interaction.channel.parent
        forum_id = self._forum_ids.get(key)
        in_right_forum = forum_id and parent and parent.id == forum_id
        in_lfg_thread  = interaction.channel.name.lower() == "recherche joueurs"

        if not in_right_forum or not in_lfg_thread:
            await interaction.response.send_message(
                embed=hermes_embed(
                    description=(
                        f"❌ Cette commande est réservée au topic **Recherche Joueurs** "
                        f"dans le forum **{game['name']}**."
                    ),
                    color=Colors.RED,
                ),
                ephemeral=True,
            )
            return

        # Vérification cooldown
        remaining = self._cooldown_remaining(key)
        if remaining > 0:
            minutes, seconds = divmod(remaining, 60)
            await interaction.response.send_message(
                embed=hermes_embed(
                    description=f"⏳ Le rôle **{game['name']}** a déjà été pingé récemment.\nProchain ping dans **{minutes}m {seconds}s**.",
                    color=Colors.ORANGE,
                ),
                ephemeral=True,
            )
            return

        # Récupération du rôle
        role = discord.utils.get(interaction.guild.roles, name=game["role_name"])
        if not role:
            await interaction.response.send_message(
                embed=hermes_embed(
                    description=f"❌ Rôle **{game['name']}** introuvable. Contacte un administrateur.",
                    color=Colors.RED,
                ),
                ephemeral=True,
            )
            return

        # Ping
        self._cooldowns[key] = datetime.utcnow()
        embed = hermes_embed(
            title=f"{game['emoji']}  Recherche de joueurs — {game['name']}",
            description=f"{interaction.user.mention} cherche des joueurs pour une partie !",
            color=game["color"],
            footer_extra=f"Prochain ping disponible dans 1h",
        )
        await interaction.response.send_message(
            content=role.mention,
            embed=embed,
            allowed_mentions=discord.AllowedMentions(roles=True),
        )

    # ── Slash commands ────────────────────────────────────────────────────────

    @app_commands.command(name="dbd", description="Ping les joueurs Dead by Daylight pour une partie")
    @command_enabled(guild_specific=True)
    async def dbd(self, interaction: discord.Interaction):
        await self._lfg_ping(interaction, "dbd")

    @app_commands.command(name="lol", description="Ping les joueurs League of Legends pour une partie")
    @command_enabled(guild_specific=True)
    async def lol(self, interaction: discord.Interaction):
        await self._lfg_ping(interaction, "lol")

    @app_commands.command(name="warframe", description="Ping les joueurs Warframe pour une partie")
    @command_enabled(guild_specific=True)
    async def warframe(self, interaction: discord.Interaction):
        await self._lfg_ping(interaction, "warframe")

    @app_commands.command(name="overwatch", description="Ping les joueurs Overwatch pour une partie")
    @command_enabled(guild_specific=True)
    async def overwatch(self, interaction: discord.Interaction):
        await self._lfg_ping(interaction, "overwatch")

    @app_commands.command(name="fortnite", description="Ping les joueurs Fortnite pour une partie")
    @command_enabled(guild_specific=True)
    async def fortnite(self, interaction: discord.Interaction):
        await self._lfg_ping(interaction, "fortnite")

    @app_commands.command(name="minecraft", description="Ping les joueurs Minecraft pour une partie")
    @command_enabled(guild_specific=True)
    async def minecraft(self, interaction: discord.Interaction):
        await self._lfg_ping(interaction, "minecraft")


async def setup(bot: commands.Bot):
    await bot.add_cog(GameLFG(bot))
