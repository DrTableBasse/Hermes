"""Reaction roles — poste/maintient l'embed de rôles dans le salon dédié.

Rôles de notification fixes ; rôles de jeux lus dans ``GameManager`` (``site_games`` : jeux
actifs avec émoji, dans l'ordre du site). Le message existant est réutilisé et seulement
modifié quand la liste change.
"""
import asyncio
import logging
import os

import discord
from discord.ext import commands, tasks

from cogs.fun import game_manager
from utils import settings
from utils.embed_style import Colors, hermes_embed

logger = logging.getLogger(__name__)

GUILD_ID = int(os.getenv('GUILD_ID', '0'))

EMBED_TITLE = "🎮 Rôles par Réaction"

# Pause entre deux réactions ajoutées (limite de débit de Discord).
REACTION_DELAY = 0.5

# emoji -> role_name (ordre d'affichage conservé)
NOTIFICATION_ROLES: dict[str, str] = {
    "⭐": "annonces globales",
    "📺": "annonces streams/vidéos",
    "🎭": "Annonce Animation",
}


def _build_embed(games: list[tuple[str, str, int | None]]) -> discord.Embed:
    """``games`` : ``(émoji, nom, id du rôle)`` des jeux actifs (``GameManager.reaction_games``)."""
    notif_lines = "\n".join(f"{e}  **{r}**" for e, r in NOTIFICATION_ROLES.items())
    game_lines  = "\n".join(f"{e}  **{name}**" for e, name, _ in games) or "—"

    embed = hermes_embed(
        title=EMBED_TITLE,
        description=(
            "Réagissez avec l'emoji correspondant pour obtenir ou retirer un rôle.\n"
            "Cliquez à nouveau sur l'emoji pour retirer le rôle."
        ),
        color=Colors.BLUE,
        footer_extra="Rôles automatiques",
    )
    embed.add_field(name="📢 Notifications", value=notif_lines, inline=False)
    embed.add_field(name="🎮 Rôles Jeux",    value=game_lines,  inline=False)
    return embed


def _same_content(a: discord.Embed, b: discord.Embed) -> bool:
    """Même titre, texte et champs (l'horodatage ne compte pas)."""
    def fields(e):
        return [(f.name, f.value) for f in e.fields]
    return (a.title, a.description, fields(a)) == (b.title, b.description, fields(b))


class ReactionRoles(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.message_id: int | None = None
        self.channel_id: int | None = None
        self._refresh_lock = asyncio.Lock()
        self._setup.start()

    def cog_unload(self):
        self._setup.cancel()

    @tasks.loop(count=1)
    async def _setup(self):
        await self.bot.wait_until_ready()
        await settings.ready.wait()  # salon des rôles lu en base, pas le défaut du registre
        try:
            await asyncio.wait_for(game_manager.ready.wait(), timeout=120)
        except asyncio.TimeoutError:
            logger.warning("ReactionRoles: jeux non chargés, message posté sans rôles de jeux")
        guild = self.bot.get_guild(GUILD_ID)
        if not guild:
            logger.warning("ReactionRoles: guild introuvable")
            return

        channel = await settings.configured_channel(guild, 'reaction_role_channel')
        if not channel or not isinstance(channel, discord.TextChannel):
            logger.warning(f"ReactionRoles: salon {settings.get('reaction_role_channel')} introuvable ou mauvais type")
            return

        self.channel_id = channel.id
        await self._ensure_roles(guild)
        await self.refresh()

    def _games(self) -> list[tuple[str, str, int | None]]:
        manager = self.bot.get_cog('GameManager')
        return manager.reaction_games() if manager else []

    async def _ensure_roles(self, guild: discord.Guild):
        """Crée les rôles de notification manquants (les rôles de jeux relèvent de GameManager)."""
        for role_name in NOTIFICATION_ROLES.values():
            if not discord.utils.get(guild.roles, name=role_name):
                try:
                    await guild.create_role(
                        name=role_name,
                        mentionable=True,
                        reason="Rôle reaction créé automatiquement par Hermes",
                    )
                    logger.info(f"Rôle créé : '{role_name}'")
                    await asyncio.sleep(0.3)
                except discord.Forbidden:
                    logger.warning(f"Permission refusée pour créer le rôle '{role_name}'")
                except discord.HTTPException as e:
                    logger.error(f"Erreur création rôle '{role_name}': {e}")

    async def refresh(self):
        """Met le message et ses réactions en accord avec la liste des jeux (appelé par GameManager)."""
        if not self.channel_id:
            return  # démarrage pas encore fait : _setup s'en chargera
        channel = self.bot.get_channel(self.channel_id)
        if channel is None:
            return
        async with self._refresh_lock:
            games = self._games()
            msg = await self._ensure_message(channel, _build_embed(games))
            if msg:
                await self._sync_reactions(msg, [*NOTIFICATION_ROLES, *(e for e, _, _ in games)])

    async def _ensure_message(self, channel: discord.TextChannel, embed: discord.Embed):
        """Trouve l'embed existant (modifié seulement s'il diffère) ou en poste un nouveau."""
        existing: discord.Message | None = None
        async for msg in channel.history(limit=100):
            if (
                msg.author == self.bot.user
                and msg.embeds
                and msg.embeds[0].title == EMBED_TITLE
            ):
                existing = msg
                break

        if existing:
            self.message_id = existing.id
            if not _same_content(existing.embeds[0], embed):
                try:
                    await existing.edit(embed=embed)
                    logger.info(f"ReactionRoles: message existant mis à jour ({existing.id})")
                except discord.HTTPException:
                    pass
            return existing
        try:
            msg = await channel.send(embed=embed)
            self.message_id = msg.id
            logger.info(f"ReactionRoles: nouveau message posté ({msg.id})")
            return msg
        except discord.Forbidden:
            logger.warning("ReactionRoles: permission refusée pour poster dans le salon")
            return None

    async def _sync_reactions(self, msg: discord.Message, emojis: list[str]):
        """Ajoute les réactions manquantes (dans l'ordre) et retire celles du bot devenues inutiles."""
        mine = {str(r.emoji) for r in msg.reactions if r.me}
        for emoji in [str(r.emoji) for r in msg.reactions if r.me and str(r.emoji) not in emojis]:
            try:
                await msg.remove_reaction(emoji, self.bot.user)
            except discord.HTTPException as e:
                logger.warning(f"Impossible de retirer la réaction {emoji}: {e}")
        for emoji in emojis:
            if emoji not in mine:
                try:
                    await msg.add_reaction(emoji)
                    await asyncio.sleep(REACTION_DELAY)
                except discord.HTTPException as e:
                    logger.warning(f"Impossible d'ajouter la réaction {emoji}: {e}")

    def _role_for(self, guild: discord.Guild, emoji: str) -> discord.Role | None:
        """Rôle d'un émoji : notification par nom, jeu par identifiant (``site_games``)."""
        name = NOTIFICATION_ROLES.get(emoji)
        if name:
            return discord.utils.get(guild.roles, name=name)
        for game_emoji, _, role_id in self._games():
            if game_emoji == emoji:
                return guild.get_role(role_id) if role_id else None
        return None

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.message_id != self.message_id:
            return
        if payload.user_id == self.bot.user.id:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        role = self._role_for(guild, str(payload.emoji))
        if not role:
            return
        member = guild.get_member(payload.user_id)
        if not member:
            return

        try:
            await member.add_roles(role, reason="Reaction role")
        except discord.Forbidden:
            pass

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        if payload.message_id != self.message_id:
            return
        if payload.user_id == self.bot.user.id:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        role = self._role_for(guild, str(payload.emoji))
        if not role:
            return
        member = guild.get_member(payload.user_id)
        if not member:
            return

        try:
            await member.remove_roles(role, reason="Reaction role retiré")
        except discord.Forbidden:
            pass


async def setup(bot: commands.Bot):
    await bot.add_cog(ReactionRoles(bot))
