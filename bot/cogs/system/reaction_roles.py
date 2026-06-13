"""Reaction roles — poste/maintient l'embed de rôles dans le salon dédié."""
import asyncio
import logging
import os

import discord
from discord.ext import commands, tasks

from utils.embed_style import Colors, FOOTER_TEXT, hermes_embed

logger = logging.getLogger(__name__)

GUILD_ID = int(os.getenv('GUILD_ID', '0'))
REACTION_ROLE_CHANNEL_ID = int(os.getenv('REACTION_ROLE_CHANNEL_ID', '836712775194771486'))

EMBED_TITLE = "🎮 Rôles par Réaction"

# emoji -> role_name (ordre d'affichage conservé)
NOTIFICATION_ROLES: dict[str, str] = {
    "⭐": "Annonces Globales",
    "📺": "Annonces Streams/Vidéos",
    "🎭": "Annonce Animation",
}

GAME_ROLES: dict[str, str] = {
    "🔪": "Dead by Daylight",
    "⚔️": "League of Legends",
    "🚀": "Warframe",
    "🌀": "Overwatch",
    "🏹": "Fortnite",
    "⛏️": "Minecraft",
}

ALL_ROLES: dict[str, str] = {**NOTIFICATION_ROLES, **GAME_ROLES}


def _build_embed() -> discord.Embed:
    notif_lines = "\n".join(f"{e}  **{r}**" for e, r in NOTIFICATION_ROLES.items())
    game_lines  = "\n".join(f"{e}  **{r}**" for e, r in GAME_ROLES.items())

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


class ReactionRoles(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.message_id: int | None = None
        self._setup.start()

    def cog_unload(self):
        self._setup.cancel()

    @tasks.loop(count=1)
    async def _setup(self):
        await self.bot.wait_until_ready()
        guild = self.bot.get_guild(GUILD_ID)
        if not guild:
            logger.warning("ReactionRoles: guild introuvable")
            return

        channel = guild.get_channel(REACTION_ROLE_CHANNEL_ID)
        if not channel or not isinstance(channel, discord.TextChannel):
            logger.warning(f"ReactionRoles: salon {REACTION_ROLE_CHANNEL_ID} introuvable ou mauvais type")
            return

        await self._ensure_roles(guild)
        await self._ensure_message(channel)

    async def _ensure_roles(self, guild: discord.Guild):
        """Crée les rôles manquants."""
        for role_name in ALL_ROLES.values():
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

    async def _ensure_message(self, channel: discord.TextChannel):
        """Trouve l'embed existant ou en poste un nouveau, puis s'assure que les réactions sont présentes."""
        existing: discord.Message | None = None
        async for msg in channel.history(limit=100):
            if (
                msg.author == self.bot.user
                and msg.embeds
                and msg.embeds[0].title == EMBED_TITLE
            ):
                existing = msg
                break

        embed = _build_embed()

        if existing:
            self.message_id = existing.id
            try:
                await existing.edit(embed=embed)
            except discord.HTTPException:
                pass
            logger.info(f"ReactionRoles: message existant mis à jour ({existing.id})")
        else:
            try:
                msg = await channel.send(embed=embed)
                self.message_id = msg.id
                logger.info(f"ReactionRoles: nouveau message posté ({msg.id})")
            except discord.Forbidden:
                logger.warning("ReactionRoles: permission refusée pour poster dans le salon")
                return

        await self._ensure_reactions(channel)

    async def _ensure_reactions(self, channel: discord.TextChannel):
        """Ajoute les réactions manquantes au message."""
        if not self.message_id:
            return
        try:
            msg = await channel.fetch_message(self.message_id)
        except discord.HTTPException:
            return

        existing_emojis = {str(r.emoji) for r in msg.reactions if r.me}
        for emoji in ALL_ROLES:
            if emoji not in existing_emojis:
                try:
                    await msg.add_reaction(emoji)
                    await asyncio.sleep(0.5)
                except discord.HTTPException as e:
                    logger.warning(f"Impossible d'ajouter la réaction {emoji}: {e}")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.message_id != self.message_id:
            return
        if payload.user_id == self.bot.user.id:
            return

        emoji = str(payload.emoji)
        role_name = ALL_ROLES.get(emoji)
        if not role_name:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        member = guild.get_member(payload.user_id)
        if not member:
            return
        role = discord.utils.get(guild.roles, name=role_name)
        if not role:
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

        emoji = str(payload.emoji)
        role_name = ALL_ROLES.get(emoji)
        if not role_name:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        member = guild.get_member(payload.user_id)
        if not member:
            return
        role = discord.utils.get(guild.roles, name=role_name)
        if not role:
            return

        try:
            await member.remove_roles(role, reason="Reaction role retiré")
        except discord.Forbidden:
            pass


async def setup(bot: commands.Bot):
    await bot.add_cog(ReactionRoles(bot))
