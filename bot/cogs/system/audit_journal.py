"""Journal unique : entrées du journal d'audit Discord et purge quotidienne.

Chaque entrée est lue une fois : d'abord comme sanction (fusion avec la ligne
site/hermes), puis pour les changements du serveur (audit_to_events). Les deux
lectures ne se recouvrent pas : une même entrée peut donner une sanction ET un
changement de pseudo, jamais deux fois le même évènement.
"""
import asyncio
import logging
from typing import Optional

import discord
from discord.ext import commands, tasks

from config import GUILD_ID
from utils.audit_events import (
    attach_deleted_by, attach_discord_entry, map_audit_action, purge_older_than, record, timeout_change,
)
from utils.server_events import audit_to_events

logger = logging.getLogger(__name__)

RETENTION_DAYS = 365
# Une action du site passe par l'API du bot : l'entrée d'audit arrive souvent
# avant que web-api n'écrive sa ligne. On réessaie une fois après ce délai.
MERGE_RETRY_S = 10
# Action Discord → action Hermes correspondante, pour le rapprochement.
_MERGE_ACTIONS = {"message_bulk_delete": "clear"}
# La ligne message/delete (évènement direct) arrive en général avant l'entrée d'audit ;
# sinon on réessaie une fois après ce délai (fenêtre de rapprochement : 10 s).
DELETED_BY_RETRY_S = 3

_permission_warned = False


def should_merge(entry_user_id: Optional[int], bot_user_id: int) -> bool:
    """Vrai si l'entrée d'audit a été produite par le bot lui-même."""
    return entry_user_id is not None and entry_user_id == bot_user_id


def classify_sanction(entry) -> Optional[tuple]:
    """(kind, action) pour une sanction, sinon None."""
    if entry.action == discord.AuditLogAction.member_update:
        change = timeout_change(entry.before, entry.after)
        return ("sanction", change) if change else None
    return map_audit_action(entry.action)


def _name(obj) -> Optional[str]:
    return getattr(obj, "display_name", None) or getattr(obj, "name", None)


def _int_id(obj) -> Optional[int]:
    """Identifiant entier de l'objet, sinon None (une invitation a un `id` texte : son code)."""
    value = getattr(obj, "id", None)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _as_dict(diff) -> dict:
    """AuditLogDiff (itérable en paires) → dict ; tolère None et les objets simples."""
    if diff is None:
        return {}
    try:
        return dict(iter(diff))
    except TypeError:
        return dict(vars(diff))


def warn_if_audit_log_hidden(guild) -> bool:
    """Vrai si le bot ne peut pas lire le journal d'audit ; avertit une seule fois."""
    global _permission_warned
    missing = not guild.me.guild_permissions.view_audit_log
    if missing and not _permission_warned:
        _permission_warned = True
        logger.warning(
            "Journal : permission Voir les logs du serveur manquante : "
            "sanctions natives non journalisées"
        )
    return missing


async def purge_once() -> Optional[int]:
    """Purge les lignes trop anciennes ; ne lève jamais (la boucle doit survivre)."""
    try:
        count = await purge_older_than(RETENTION_DAYS)
    except Exception as e:
        logger.warning("Journal : purge impossible : %s", e)
        return None
    logger.info("Journal : %d ligne(s) de plus de %d jours supprimée(s)", count, RETENTION_DAYS)
    return count


class AuditJournal(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        guild = self.bot.get_guild(int(GUILD_ID)) if GUILD_ID else None
        if guild and guild.me:
            warn_if_audit_log_hidden(guild)
        self.purge_task.start()

    async def cog_unload(self):
        self.purge_task.cancel()

    @tasks.loop(hours=24)
    async def purge_task(self):
        await purge_once()

    @purge_task.before_loop
    async def _before_purge(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_audit_log_entry_create(self, entry):
        sanction = classify_sanction(entry)
        if sanction:
            await self._journal(entry, *sanction)
        if entry.action == discord.AuditLogAction.message_delete:
            await self._complete_message_delete(entry)
        before, after = _as_dict(entry.before), _as_dict(entry.after)
        for kind, action, details in audit_to_events(entry.action, before, after):
            await self._record_change(entry, kind, action, details, before, after)

    async def _record_change(self, entry, kind: str, action: str, details: dict, before: dict, after: dict):
        """Changement du serveur lu dans le journal d'audit (aucune ligne Hermes à rapprocher)."""
        target, target_id, target_name = entry.target, _int_id(entry.target), _name(entry.target)
        if target_name is None:  # cible supprimée ou invitation : nom dans les valeurs
            for values in (after, before):
                target_name = values.get("name") or values.get("code")
                if target_name:
                    break
        channel_id = channel_name = None
        if kind in ("channel", "thread", "permission"):
            # Le salon (ou fil) est la cible Discord : il est aussi reporté en salon pour le filtre.
            channel_id, channel_name = target_id, target_name
        if kind == "permission":
            # Surcharge de salon : la cible est le rôle ou le membre visé.
            target = getattr(entry, "extra", None)
            target_id, target_name = _int_id(target), _name(target)
        await record(
            kind=kind, action=action, source="discord",
            actor_id=entry.user_id, actor_name=_name(entry.user),
            target_id=target_id, target_name=target_name,
            channel_id=channel_id, channel_name=channel_name,
            details={**details, "reason": entry.reason, "discord_audit_id": entry.id},
        )

    async def _complete_message_delete(self, entry):
        """Suppression par un modérateur : `deleted_by` sur les lignes message/delete.

        Limite connue : Discord ne réémet pas l'évènement quand il regroupe une
        suppression suivante dans la même entrée (seul `count` augmente) ; ces
        suppressions-là restent sans `deleted_by`.
        """
        channel = getattr(getattr(entry, "extra", None), "channel", None)
        for attempt in range(2):
            if attempt:
                await asyncio.sleep(DELETED_BY_RETRY_S)
            if await attach_deleted_by(
                author_id=_int_id(entry.target), author_name=_name(entry.target),
                channel_id=_int_id(channel),
                moderator_id=entry.user_id, moderator_name=_name(entry.user),
            ):
                return

    async def _journal(self, entry, kind: str, action: str):
        target_id = _int_id(entry.target)
        if should_merge(entry.user_id, self.bot.user.id) and await self._attach(entry, action, target_id):
            return
        details = {"reason": entry.reason, "discord_audit_id": entry.id}
        count = getattr(getattr(entry, "extra", None), "count", None)
        if action in ("message_delete", "message_bulk_delete") and isinstance(count, int):
            # Discord regroupe les suppressions successives : nombre de messages de l'entrée.
            details["count"] = count
        channel = None
        if action == "message_delete":
            channel = getattr(getattr(entry, "extra", None), "channel", None)
        elif action == "message_bulk_delete":  # la cible Discord est le salon
            channel = getattr(getattr(entry, "extra", None), "channel", None) or entry.target
        await record(
            kind=kind, action=action, source="discord",
            actor_id=entry.user_id, actor_name=_name(entry.user),
            target_id=target_id, target_name=_name(entry.target),
            channel_id=_int_id(channel), channel_name=_name(channel),
            details=details,
        )

    async def _attach(self, entry, action: str, target_id: Optional[int]) -> bool:
        merge_action = _MERGE_ACTIONS.get(action, action)
        # /clear n'a pas de cible : la ligne Hermes porte target_id NULL.
        merge_target = None if merge_action != action else target_id
        for attempt in range(2):
            if attempt:
                await asyncio.sleep(MERGE_RETRY_S)
            if await attach_discord_entry(action=merge_action, target_id=merge_target, audit_id=entry.id):
                return True
        return False


async def setup(bot):
    await bot.add_cog(AuditJournal(bot))
