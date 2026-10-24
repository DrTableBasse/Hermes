import io
import os
import logging
import discord
from discord.ext import commands
from utils.embed_style import hermes_embed, Colors

logger = logging.getLogger(__name__)
MESSAGE_LOG_CHANNEL_ID = int(os.getenv('MESSAGE_LOG_CHANNEL_ID', '777133504634945627'))
FIELD_LIMIT = 1024


def _clip(text: str | None) -> str:
    if not text:
        return "*(vide)*"
    return text if len(text) <= FIELD_LIMIT else text[:FIELD_LIMIT - 1] + "…"


def _attachments_field(message: discord.Message) -> str | None:
    if not message.attachments:
        return None
    return _clip("\n".join(f"📎 {a.filename}" for a in message.attachments))


class MessageLogsCog(commands.Cog):
    """Logs edited / deleted messages. Raw events cover messages absent from the cache."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _send(self, embed: discord.Embed, file: discord.File | None = None):
        channel = self.bot.get_channel(MESSAGE_LOG_CHANNEL_ID)
        if channel is None:
            logger.warning("MessageLogs: canal log %s introuvable", MESSAGE_LOG_CHANNEL_ID)
            return
        try:
            if file is not None:
                await channel.send(embed=embed, file=file)
            else:
                await channel.send(embed=embed)
        except discord.HTTPException as e:
            logger.warning("MessageLogs: envoi impossible: %s", e)

    def _ignored(self, guild_id: int | None, channel_id: int) -> bool:
        return guild_id is None or channel_id == MESSAGE_LOG_CHANNEL_ID

    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload: discord.RawMessageUpdateEvent):
        if self._ignored(payload.guild_id, payload.channel_id):
            return
        data = payload.data
        author = data.get('author') or {}
        if author.get('bot') or 'content' not in data:
            return
        before = payload.cached_message
        after_content = data['content']
        if before is not None:
            if before.author.bot or before.content == after_content:
                return  # embed unfurl, pin…
        elif not data.get('edited_timestamp'):
            return  # not a real edit (link preview on an uncached message)

        author_id = int(author['id']) if author.get('id') else None
        jump = f"https://discord.com/channels/{payload.guild_id}/{payload.channel_id}/{payload.message_id}"
        embed = hermes_embed(
            title="✏️  Message modifié",
            description=f"**Auteur :** <@{author_id}>\n**Salon :** <#{payload.channel_id}>\n[Aller au message]({jump})",
            color=Colors.ORANGE,
            thumbnail_url=before.author.display_avatar.url if before else None,
            footer_extra=f"ID {payload.message_id}",
        )
        embed.add_field(
            name="Avant",
            value=_clip(before.content) if before else "*(message hors cache, contenu inconnu)*",
            inline=False,
        )
        embed.add_field(name="Après", value=_clip(after_content), inline=False)
        await self._send(embed)

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent):
        if self._ignored(payload.guild_id, payload.channel_id):
            return
        message = payload.cached_message
        if message is not None and message.author.bot:
            return

        if message is None:
            embed = hermes_embed(
                title="🗑️  Message supprimé",
                description=f"**Salon :** <#{payload.channel_id}>\n*(message hors cache, contenu inconnu)*",
                color=Colors.RED,
                footer_extra=f"ID {payload.message_id}",
            )
            await self._send(embed)
            return

        embed = hermes_embed(
            title="🗑️  Message supprimé",
            description=f"**Auteur :** {message.author.mention}\n**Salon :** <#{payload.channel_id}>",
            color=Colors.RED,
            thumbnail_url=message.author.display_avatar.url,
            footer_extra=f"ID {payload.message_id}",
        )
        embed.add_field(name="Contenu", value=_clip(message.content), inline=False)
        attachments = _attachments_field(message)
        if attachments:
            embed.add_field(name="Pièces jointes", value=attachments, inline=False)
        await self._send(embed)

    @commands.Cog.listener()
    async def on_raw_bulk_message_delete(self, payload: discord.RawBulkMessageDeleteEvent):
        if self._ignored(payload.guild_id, payload.channel_id):
            return
        cached = sorted(payload.cached_messages, key=lambda m: m.created_at)
        embed = hermes_embed(
            title="🧹  Suppression en masse",
            description=(
                f"**Salon :** <#{payload.channel_id}>\n"
                f"**Messages :** {len(payload.message_ids)} "
                f"(dont {len(cached)} en cache, détail en pièce jointe)"
            ),
            color=Colors.DARK_RED,
        )
        file = None
        if cached:
            lines = [
                f"[{m.created_at:%Y-%m-%d %H:%M}] {m.author} ({m.author.id}): {m.content}"
                + "".join(f" [📎 {a.filename}]" for a in m.attachments)
                for m in cached
            ]
            file = discord.File(io.BytesIO("\n".join(lines).encode('utf-8')), filename="messages_supprimes.txt")
        await self._send(embed, file)


async def setup(bot):
    await bot.add_cog(MessageLogsCog(bot))
