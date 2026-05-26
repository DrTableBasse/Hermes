"""Prometheus metrics — updated every 60 s by MetricsUpdaterCog."""
import logging
from prometheus_client import Gauge

logger = logging.getLogger(__name__)

members_total        = Gauge('hermes_members_total',          'Total server members currently tracked')
messages_total       = Gauge('hermes_messages_total',         'Total messages sent across all users')
xp_total             = Gauge('hermes_xp_total',               'Total XP distributed across all users')
voice_hours_total    = Gauge('hermes_voice_hours_total',      'Total voice hours across all users')
active_quests_total  = Gauge('hermes_active_quests_total',    'Number of active quests this week')
quest_completions_week = Gauge('hermes_quest_completions_week', 'Quest completions this week')
warns_total          = Gauge('hermes_warns_total',            'Total warnings ever issued')
bot_ready            = Gauge('hermes_bot_ready',              '1 if bot is connected and ready, 0 otherwise')


async def refresh():
    """Query the DB and update all gauges. Must run after init_database()."""
    try:
        from utils.database import db_manager

        members = await db_manager.fetchval(
            "SELECT COUNT(*) FROM user_voice_data WHERE is_member = TRUE"
        )
        members_total.set(members or 0)

        msgs = await db_manager.fetchval(
            "SELECT COALESCE(SUM(message_count), 0) FROM user_message_stats"
        )
        messages_total.set(msgs or 0)

        xp = await db_manager.fetchval(
            "SELECT COALESCE(SUM(total_xp), 0) FROM user_xp"
        )
        xp_total.set(xp or 0)

        hours = await db_manager.fetchval(
            "SELECT COALESCE(SUM(total_time) / 3600.0, 0) FROM user_voice_data"
        )
        voice_hours_total.set(float(hours or 0))

        quests = await db_manager.fetchval(
            "SELECT COUNT(*) FROM weekly_quests WHERE is_active = TRUE"
        )
        active_quests_total.set(quests or 0)

        completions = await db_manager.fetchval(
            """SELECT COUNT(*) FROM user_quest_progress uqp
               JOIN weekly_quests q ON q.id = uqp.quest_id
               WHERE uqp.completed = TRUE
                 AND q.week_start >= date_trunc('week', CURRENT_DATE)"""
        )
        quest_completions_week.set(completions or 0)

        warns = await db_manager.fetchval("SELECT COUNT(*) FROM warn")
        warns_total.set(warns or 0)

    except Exception as e:
        logger.warning("metrics refresh error: %s", e)
