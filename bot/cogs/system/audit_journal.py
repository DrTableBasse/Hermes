"""Journal unique : entrées du journal d'audit Discord et purge quotidienne."""
import asyncio
import logging
from typing import Callable, Optional

import discord
from discord.ext import commands, tasks

from config import GUILD_ID
from utils.audit_events import (
    attach_discord_entry, map_audit_action, purge_older_than, record, timeout_change,
)

logger = logging.getLogger(__name__)

RETENTION_DAYS = 365
# Une action du site passe par l'API du bot : l'entrée d'audit arrive souvent
# avant que web-api n'écrive sa ligne. On réessaie une fois après ce délai.
MERGE_RETRY_S = 10
# Action Discord → action Hermes correspondante, pour le rapprochement.
_MERGE_ACTIONS = {"message_bulk_delete": "clear"}

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


# Classifieurs essayés dans l'ordre ; le premier qui reconnaît l'entrée l'emporte,
# une entrée n'est donc journalisée qu'une fois. La tâche 4 ajoute les siens ici.
CLASSIFIERS: list[Callable] = [classify_sanction]


def _name(obj) -> Optional[str]:
    return getattr(obj, "display_name", None) or getattr(obj, "name", None)


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
        for classify in CLASSIFIERS:
            mapped = classify(entry)
            if mapped:
                await self._journal(entry, *mapped)
                return

    async def _journal(self, entry, kind: str, action: str):
        target_id = getattr(entry.target, "id", None)
        if should_merge(entry.user_id, self.bot.user.id) and await self._attach(entry, action, target_id):
            return
        await record(
            kind=kind, action=action, source="discord",
            actor_id=entry.user_id, actor_name=_name(entry.user),
            target_id=target_id, target_name=_name(entry.target),
            details={"reason": entry.reason, "discord_audit_id": entry.id},
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
