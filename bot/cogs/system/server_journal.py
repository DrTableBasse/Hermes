"""Journal unique : messages modifiés/supprimés, vocal, arrivées et départs.

Évènements sans entrée d'audit Discord ; les changements structurels sont lus
dans le journal d'audit (audit_journal.py). Les cogs existants (message_logs,
voice, invite_tracker, welcome) gardent leur comportement : on ajoute des écouteurs.
"""
import logging
from typing import Optional

import discord
from discord.ext import commands

from utils.audit_events import record
from utils.server_events import VOICE_FLAG_ATTRS, message_snapshot, voice_actions

logger = logging.getLogger(__name__)


def _snapshot_of(message) -> dict:
    return message_snapshot(message.content, [a.filename for a in message.attachments], len(message.embeds))


def _payload_snapshot(data: dict) -> dict:
    return message_snapshot(
        data.get("content"),
        [a.get("filename") for a in data.get("attachments") or []],
        len(data.get("embeds") or []),
    )


def _payload_author_name(data: dict) -> Optional[str]:
    author = data.get("author") or {}
    member = data.get("member") or {}
    return member.get("nick") or author.get("global_name") or author.get("username")


class ServerJournal(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _channel(self, channel_id: int) -> tuple:
        channel = self.bot.get_channel(channel_id)
        return channel_id, getattr(channel, "name", None)

    # ── Messages ────────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload):
        data = payload.data
        author = data.get("author") or {}
        if payload.guild_id is None or author.get("bot") or "content" not in data:
            return
        before = payload.cached_message
        if before is not None:
            if before.author.bot or before.content == data["content"]:
                return  # embed déplié, épinglage… : pas une édition
        elif not data.get("edited_timestamp"):
            return  # aperçu de lien sur un message hors cache
        channel_id, channel_name = self._channel(payload.channel_id)
        await record(
            kind="message", action="edit", source="discord",
            actor_id=before.author.id if before else (int(author["id"]) if author.get("id") else None),
            actor_name=before.author.display_name if before else _payload_author_name(data),
            channel_id=channel_id, channel_name=channel_name,
            details={
                "message_id": payload.message_id,
                "avant": _snapshot_of(before) if before else message_snapshot(None, [], 0),
                "après": _payload_snapshot(data),
            },
        )

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload):
        message = payload.cached_message
        if payload.guild_id is None or (message is not None and message.author.bot):
            return
        channel_id, channel_name = self._channel(payload.channel_id)
        await record(
            kind="message", action="delete", source="discord",
            actor_id=message.author.id if message else None,
            actor_name=message.author.display_name if message else None,
            channel_id=channel_id, channel_name=channel_name,
            details={
                "message_id": payload.message_id,
                **(_snapshot_of(message) if message else message_snapshot(None, [], 0)),
            },
        )

    @commands.Cog.listener()
    async def on_raw_bulk_message_delete(self, payload):
        if payload.guild_id is None:
            return
        channel_id, channel_name = self._channel(payload.channel_id)
        messages = [
            {"author_id": m.author.id, "author_name": m.author.display_name, **_snapshot_of(m)}
            for m in payload.cached_messages if not m.author.bot
        ]
        await record(
            kind="message", action="bulk_delete", source="discord",
            actor_id=None, actor_name=None,
            channel_id=channel_id, channel_name=channel_name,
            details={"count": len(payload.message_ids), "messages": messages},
        )

    # ── Vocal ───────────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        for action in voice_actions(before, after):
            channel = before.channel if action == "leave" else after.channel
            details = {}
            if action == "move":
                details = {"from_channel": before.channel.name, "from_channel_id": before.channel.id}
            elif action in VOICE_FLAG_ATTRS:
                details = {"active": bool(getattr(after, VOICE_FLAG_ATTRS[action]))}
            # Sourdine imposée par le serveur : l'auteur (un modérateur) n'est pas connu ici.
            by_server = action.startswith("server_")
            await record(
                kind="voice", action=action, source="discord",
                actor_id=None if by_server else member.id,
                actor_name=None if by_server else member.display_name,
                target_id=member.id if by_server else None,
                target_name=member.display_name if by_server else None,
                channel_id=getattr(channel, "id", None), channel_name=getattr(channel, "name", None),
                details=details,
            )

    # ── Membres ─────────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_member_join_tracked(self, member, used_invite):
        """Émis par invite_tracker pour chaque arrivée humaine, invitation comprise si connue."""
        details = {"invite_code": getattr(used_invite, "code", None)}
        inviter = getattr(used_invite, "inviter", None)
        if inviter is not None:
            details["inviter_id"] = inviter.id
            details["inviter_name"] = getattr(inviter, "display_name", None) or inviter.name
        await record(
            kind="member", action="join", source="discord",
            actor_id=member.id, actor_name=member.display_name, details=details,
        )

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        if member.bot:
            return
        await record(
            kind="member", action="leave", source="discord",
            actor_id=member.id, actor_name=member.display_name,
        )


async def setup(bot):
    await bot.add_cog(ServerJournal(bot))
