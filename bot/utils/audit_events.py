"""Journal unique des évènements (table audit_events) : écriture et helpers purs."""
import json
import logging
from datetime import datetime, timezone
from typing import Optional

import discord

from utils.database import db_manager

logger = logging.getLogger(__name__)

MASKED_COMMANDS: frozenset = frozenset({"confess"})
MAX_VALUE_LEN = 500
MASK = "[masqué]"

_AUDIT_ACTIONS = {
    discord.AuditLogAction.kick: ("sanction", "kick"),
    discord.AuditLogAction.ban: ("sanction", "ban"),
    discord.AuditLogAction.unban: ("sanction", "unban"),
    discord.AuditLogAction.message_delete: ("sanction", "message_delete"),
    discord.AuditLogAction.message_bulk_delete: ("sanction", "message_bulk_delete"),
}


def _option_text(value: object) -> str:
    if isinstance(value, discord.Attachment):
        text = value.filename
    elif isinstance(value, (discord.abc.GuildChannel, discord.Role, discord.abc.User)):
        text = f"{getattr(value, 'name', '?')} ({value.id})"
    else:
        text = str(value)
    if len(text) > MAX_VALUE_LEN:
        text = text[:MAX_VALUE_LEN] + "…"
    return text


def command_options(command_name: str, raw: dict) -> dict:
    """Options d'une commande converties en texte ; tout masqué pour les commandes anonymes."""
    if command_name in MASKED_COMMANDS:
        return {key: MASK for key in raw}
    return {key: _option_text(value) for key, value in raw.items()}


def map_audit_action(action: discord.AuditLogAction) -> Optional[tuple]:
    """(kind, action) du journal pour une entrée d'audit Discord, ou None."""
    return _AUDIT_ACTIONS.get(action)


def timeout_change(before, after) -> Optional[str]:
    """'timeout' / 'untimeout' selon l'évolution de timed_out_until, sinon None."""
    moment = datetime.now(timezone.utc)
    was = getattr(before, "timed_out_until", None)
    now = getattr(after, "timed_out_until", None)
    was_active = was is not None and was > moment
    now_active = now is not None and now > moment
    if now_active and not was_active:
        return "timeout"
    if was_active and not now_active:
        return "untimeout"
    return None


async def record(
    *,
    kind: str,
    action: str,
    source: str,
    actor_id: Optional[int],
    actor_name: Optional[str],
    target_id: Optional[int] = None,
    target_name: Optional[str] = None,
    channel_id: Optional[int] = None,
    channel_name: Optional[str] = None,
    success: bool = True,
    details: Optional[dict] = None,
) -> Optional[int]:
    """Écrit une ligne de journal. Ne lève jamais : retourne None en cas d'échec."""
    try:
        return await db_manager.fetchval(
            """
            INSERT INTO audit_events
                (kind, action, source, actor_id, actor_name, target_id, target_name,
                 channel_id, channel_name, success, details)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11::jsonb)
            RETURNING id
            """,
            kind, action, source, actor_id, actor_name, target_id, target_name,
            channel_id, channel_name, success,
            json.dumps(details or {}, ensure_ascii=False, default=str),
        )
    except Exception as e:
        logger.warning("Écriture du journal impossible (%s/%s) : %s", kind, action, e)
        return None


async def attach_discord_entry(
    *, action: str, target_id: Optional[int], audit_id: int, window_s: int = 120
) -> bool:
    """Complète la ligne site/hermes récente correspondante avec l'id d'audit Discord."""
    try:
        updated = await db_manager.fetchval(
            """
            UPDATE audit_events
            SET details = details || jsonb_build_object('discord_audit_id', $1::bigint)
            WHERE id = (
                SELECT id FROM audit_events
                WHERE source IN ('site','hermes')
                  AND action = $2
                  AND target_id IS NOT DISTINCT FROM $3
                  AND occurred_at > NOW() - make_interval(secs => $4)
                  AND NOT details ? 'discord_audit_id'
                ORDER BY occurred_at DESC
                LIMIT 1
            )
            RETURNING id
            """,
            audit_id, action, target_id, window_s,
        )
        return updated is not None
    except Exception as e:
        logger.warning("Rapprochement du journal impossible (%s) : %s", action, e)
        return False


async def purge_older_than(days: int = 365) -> int:
    """Supprime les lignes plus vieilles que `days` jours ; retourne leur nombre."""
    count = await db_manager.fetchval(
        """
        WITH d AS (
            DELETE FROM audit_events
            WHERE occurred_at < NOW() - make_interval(days => $1)
            RETURNING 1
        )
        SELECT count(*) FROM d
        """,
        days,
    )
    return int(count or 0)
