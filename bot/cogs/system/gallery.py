"""Galerie : un ✅ du staff sur un message de #galerie le publie sur le site.

Première image valide en pièce jointe → fichier dans le volume média ; sinon premier
lien de clip ; sinon rien. Un message supprimé quitte la galerie, fichier compris
(``utils.gallery.forget_message``).
"""
import asyncio
import logging
import os
import uuid
from pathlib import Path
from typing import Optional

import discord
from discord.ext import commands

from utils import settings
from utils.database import db_manager
from utils.gallery import MAX_IMAGE_BYTES, classify_clip, find_clip_url, forget_message, sniff_image

logger = logging.getLogger(__name__)

APPROVE_EMOJI = "✅"
GALLERY_DIR = Path(os.getenv("MEDIA_DIR", "/app/media")) / "gallery"
MAX_CAPTION = 500


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


class Gallery(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._startup = asyncio.create_task(self._ensure_channel())

    def cog_unload(self):
        self._startup.cancel()

    def _guild(self) -> Optional[discord.Guild]:
        return self.bot.get_guild(int(os.getenv("GUILD_ID", "0")))

    async def _ensure_channel(self):
        """Décision R5 : #galerie est créé au chargement du cog s'il manque."""
        try:
            await self.bot.wait_until_ready()
            await settings.ready.wait()
            guild = self._guild()
            if guild:
                await settings.ensure_channel(guild, "gallery_channel")
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Création du salon de la galerie impossible")

    @staticmethod
    def _is_staff(guild: discord.Guild, member: Optional[discord.Member]) -> bool:
        if member is None:
            return False
        staff = {r.id for r in (settings.get_role(guild, "admin_role"),
                                settings.get_role(guild, "mod_role")) if r}
        return any(r.id in staff for r in member.roles)

    async def _store_image(self, attachment: discord.Attachment) -> Optional[str]:
        # Taille vérifiée avant tout téléchargement.
        if attachment.size > MAX_IMAGE_BYTES:
            return None
        data = await attachment.read()
        ext = sniff_image(data)
        if ext is None or len(data) > MAX_IMAGE_BYTES:
            return None
        name = f"{uuid.uuid4()}.{ext}"
        await asyncio.to_thread(_write, GALLERY_DIR / name, data)
        return name

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        try:
            if str(payload.emoji) != APPROVE_EMOJI:
                return
            await settings.ready.wait()
            channel_id = settings.get_int("gallery_channel")
            if not channel_id or payload.channel_id != channel_id:
                return
            guild = self._guild()
            if guild is None or not self._is_staff(guild, payload.member):
                return
            await self._approve(guild, payload)
        except Exception:
            logger.exception("Validation galerie en échec (message %s)", payload.message_id)

    async def _approve(self, guild: discord.Guild, payload: discord.RawReactionActionEvent):
        if await db_manager.fetchval(
            "SELECT 1 FROM gallery_items WHERE message_id = $1", payload.message_id
        ):
            return  # déjà publié : pas de second téléchargement
        channel = guild.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        if message.author.bot:
            return

        kind = file_name = clip_url = provider = None
        for attachment in message.attachments:
            file_name = await self._store_image(attachment)
            if file_name:
                kind = "image"
                break
        if kind is None:
            clip_url = find_clip_url(message.content)
            if clip_url:
                kind, provider = "clip", classify_clip(clip_url)
        if kind is None:
            return

        inserted = await db_manager.fetchval(
            """INSERT INTO gallery_items
                   (message_id, channel_id, author_id, approved_by, kind, file_name,
                    clip_url, clip_provider, caption)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
               ON CONFLICT (message_id) DO NOTHING RETURNING id""",
            message.id, message.channel.id, message.author.id, payload.user_id, kind,
            file_name, clip_url, provider, (message.content or "")[:MAX_CAPTION] or None,
        )
        if inserted is None and file_name:
            # Course avec une autre validation : le fichier téléchargé est orphelin.
            await asyncio.to_thread((GALLERY_DIR / file_name).unlink, True)

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent):
        try:
            await forget_message(db_manager, GALLERY_DIR, payload.message_id)
        except Exception:
            logger.exception("Retrait galerie en échec (message %s)", payload.message_id)


async def setup(bot: commands.Bot):
    await bot.add_cog(Gallery(bot))
