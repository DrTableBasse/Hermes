"""Prometheus metrics — rafraîchies toutes les 60s par MetricsUpdaterCog."""
import logging
import time as _time
from prometheus_client import Gauge

logger = logging.getLogger(__name__)

# ── Scalaires — santé & activité globale ──────────────────────────────────────
bot_ready              = Gauge('hermes_bot_ready',              '1 si le bot est connecté et prêt')
members_total          = Gauge('hermes_members_total',          'Membres actuellement suivis')
members_in_voice       = Gauge('hermes_members_in_voice',       'Membres en vocal en ce moment')
messages_total         = Gauge('hermes_messages_total',         'Messages envoyés — total cumulé')
xp_total               = Gauge('hermes_xp_total',              'XP distribué — total cumulé')
xp_weekly_total        = Gauge('hermes_xp_weekly_total',       'XP distribué cette semaine')
avg_xp                 = Gauge('hermes_avg_xp',                'XP moyen par membre actif')
top_level              = Gauge('hermes_top_level',             'Niveau le plus élevé du serveur')
voice_hours_total      = Gauge('hermes_voice_hours_total',     'Heures en vocal — total cumulé')

# ── Scalaires — modération ────────────────────────────────────────────────────
warns_total            = Gauge('hermes_warns_total',           'Avertissements — total cumulé')
warns_30d              = Gauge('hermes_warns_30d',             'Avertissements ces 30 derniers jours')
users_with_warns       = Gauge('hermes_users_with_warns',      'Membres ayant au moins 1 avertissement')

# ── Scalaires — quêtes ────────────────────────────────────────────────────────
active_quests_total    = Gauge('hermes_active_quests_total',   'Quêtes actives cette semaine')
quest_completions_week = Gauge('hermes_quest_completions_week', 'Complétions de quêtes cette semaine')

# ── Scalaires — engagement ────────────────────────────────────────────────────
bumps_total            = Gauge('hermes_bumps_total',           'Bumps DISBOARD — total cumulé')
achievements_total     = Gauge('hermes_achievements_total',    'Succès débloqués — total cumulé')
achievements_7d        = Gauge('hermes_achievements_7d',       'Succès débloqués ces 7 derniers jours')
active_voice_streaks   = Gauge('hermes_active_voice_streaks',  'Membres avec un streak vocal en cours')
active_msg_streaks     = Gauge('hermes_active_msg_streaks',    'Membres avec un streak messages en cours')
max_voice_streak       = Gauge('hermes_max_voice_streak',      'Plus long streak vocal du serveur')
max_msg_streak         = Gauge('hermes_max_msg_streak',        'Plus long streak messages du serveur')

# ── Avec labels — quêtes actives ─────────────────────────────────────────────
_Q = ['quest_id', 'title', 'quest_type', 'icon']
quest_participants     = Gauge('hermes_quest_participants',    'Participants par quête', _Q)
quest_completions_cnt  = Gauge('hermes_quest_completions_cnt', 'Complétions par quête', _Q)
quest_completion_rate  = Gauge('hermes_quest_completion_rate', 'Taux de complétion par quête (%)', _Q)
quest_xp_reward        = Gauge('hermes_quest_xp_reward',      'Récompense XP par quête', _Q)

# ── Avec labels — distribution des niveaux ────────────────────────────────────
level_distribution     = Gauge('hermes_level_distribution',   'Membres par tranche de niveau', ['range'])

# ── Avec labels — avertissements par membre ───────────────────────────────────
user_warn_count        = Gauge('hermes_user_warn_count',      'Avertissements par membre', ['username', 'user_id'])

# ── Avec labels — top 15 XP ───────────────────────────────────────────────────
user_xp_top            = Gauge('hermes_user_xp_top',          'XP des 15 meilleurs membres', ['username', 'level'])

# ── Scalaires — invitations ────────────────────────────────────────────────────
invites_total          = Gauge('hermes_invites_total',         'Codes d\'invitation actifs')
invites_uses_total     = Gauge('hermes_invites_uses_total',    'Utilisations d\'invitations — total cumulé')
invites_uses_7d        = Gauge('hermes_invites_uses_7d',       'Membres ayant rejoint via invitation ces 7 derniers jours')

# ── Avec labels — top 15 inviters ─────────────────────────────────────────────
top_inviters           = Gauge('hermes_top_inviters',          'Membres ayant le plus invité', ['username', 'user_id'])

# ── Avec labels — liste des codes d'invitation actifs ─────────────────────────
invite_codes_list      = Gauge('hermes_invite_codes',          'Invitations actives par code', ['code', 'host', 'expires_at'])


async def refresh(guild=None):
    """Interroge la BDD et met à jour toutes les jauges. guild = discord.Guild or None."""
    try:
        from utils.database import db_manager

        # ── Membres ───────────────────────────────────────────────────────────
        members_total.set(
            await db_manager.fetchval("SELECT COUNT(*) FROM user_voice_data WHERE is_member = TRUE") or 0
        )

        if guild:
            members_in_voice.set(sum(
                1 for vc in guild.voice_channels
                for m in vc.members if not m.bot
            ))

        # ── Messages ──────────────────────────────────────────────────────────
        messages_total.set(
            await db_manager.fetchval(
                "SELECT COALESCE(SUM(message_count), 0) FROM user_message_stats"
            ) or 0
        )

        # ── XP ────────────────────────────────────────────────────────────────
        xp_total.set(
            await db_manager.fetchval("SELECT COALESCE(SUM(total_xp), 0) FROM user_xp") or 0
        )
        xp_weekly_total.set(
            await db_manager.fetchval("SELECT COALESCE(SUM(weekly_xp), 0) FROM user_xp") or 0
        )
        avg_xp.set(float(
            await db_manager.fetchval(
                """SELECT COALESCE(AVG(u.total_xp), 0)
                   FROM user_xp u JOIN user_voice_data v ON v.user_id = u.user_id
                   WHERE v.is_member = TRUE"""
            ) or 0
        ))
        top_level.set(
            await db_manager.fetchval("SELECT COALESCE(MAX(current_level), 0) FROM user_xp") or 0
        )

        # ── Vocal ─────────────────────────────────────────────────────────────
        voice_hours_total.set(float(
            await db_manager.fetchval(
                "SELECT COALESCE(SUM(total_time) / 3600.0, 0) FROM user_voice_data"
            ) or 0
        ))

        # ── Modération ────────────────────────────────────────────────────────
        warns_total.set(
            await db_manager.fetchval("SELECT COUNT(*) FROM warn") or 0
        )
        ts_30d = int(_time.time()) - 30 * 86400
        warns_30d.set(
            await db_manager.fetchval(
                "SELECT COUNT(*) FROM warn WHERE create_time > $1", ts_30d
            ) or 0
        )
        users_with_warns.set(
            await db_manager.fetchval("SELECT COUNT(DISTINCT user_id) FROM warn") or 0
        )

        # ── Quêtes ────────────────────────────────────────────────────────────
        active_quests_total.set(
            await db_manager.fetchval("SELECT COUNT(*) FROM weekly_quests WHERE is_active = TRUE") or 0
        )
        quest_completions_week.set(
            await db_manager.fetchval(
                """SELECT COUNT(*) FROM user_quest_progress uqp
                   JOIN weekly_quests q ON q.id = uqp.quest_id
                   WHERE uqp.completed = TRUE
                     AND q.week_start >= date_trunc('week', CURRENT_DATE)"""
            ) or 0
        )

        # ── Bumps ─────────────────────────────────────────────────────────────
        bumps_total.set(
            await db_manager.fetchval(
                "SELECT COALESCE(SUM(bump_count), 0) FROM user_bump_stats"
            ) or 0
        )

        # ── Succès ────────────────────────────────────────────────────────────
        achievements_total.set(
            await db_manager.fetchval("SELECT COUNT(*) FROM user_achievements") or 0
        )
        achievements_7d.set(
            await db_manager.fetchval(
                "SELECT COUNT(*) FROM user_achievements WHERE unlocked_at > NOW() - INTERVAL '7 days'"
            ) or 0
        )

        # ── Streaks ───────────────────────────────────────────────────────────
        active_voice_streaks.set(
            await db_manager.fetchval(
                "SELECT COUNT(*) FROM user_streaks WHERE current_streak > 0"
            ) or 0
        )
        active_msg_streaks.set(
            await db_manager.fetchval(
                "SELECT COUNT(*) FROM user_message_streaks WHERE current_streak > 0"
            ) or 0
        )
        max_voice_streak.set(
            await db_manager.fetchval(
                "SELECT COALESCE(MAX(max_streak), 0) FROM user_streaks"
            ) or 0
        )
        max_msg_streak.set(
            await db_manager.fetchval(
                "SELECT COALESCE(MAX(max_streak), 0) FROM user_message_streaks"
            ) or 0
        )

        # ── Labeled : quêtes actives ──────────────────────────────────────────
        quests = await db_manager.fetch("""
            SELECT
                q.id, q.title, q.quest_type, q.icon, q.xp_reward,
                COUNT(DISTINCT uqp.user_id)                                        AS participants,
                COUNT(DISTINCT uqp.user_id) FILTER (WHERE uqp.completed = TRUE)    AS completions
            FROM weekly_quests q
            LEFT JOIN user_quest_progress uqp ON uqp.quest_id = q.id
            WHERE q.is_active = TRUE
            GROUP BY q.id, q.title, q.quest_type, q.icon, q.xp_reward
            ORDER BY q.id
        """)
        quest_participants._metrics.clear()
        quest_completions_cnt._metrics.clear()
        quest_completion_rate._metrics.clear()
        quest_xp_reward._metrics.clear()
        for q in quests:
            lbl = dict(quest_id=str(q['id']), title=q['title'],
                       quest_type=q['quest_type'], icon=q['icon'])
            p, c = q['participants'] or 0, q['completions'] or 0
            quest_participants.labels(**lbl).set(p)
            quest_completions_cnt.labels(**lbl).set(c)
            quest_completion_rate.labels(**lbl).set(round(c / p * 100, 1) if p else 0.0)
            quest_xp_reward.labels(**lbl).set(q['xp_reward'] or 0)

        # ── Labeled : distribution des niveaux ────────────────────────────────
        levels = await db_manager.fetch("""
            SELECT
                CASE
                    WHEN u.current_level BETWEEN 1  AND 5  THEN '1-5'
                    WHEN u.current_level BETWEEN 6  AND 10 THEN '6-10'
                    WHEN u.current_level BETWEEN 11 AND 20 THEN '11-20'
                    WHEN u.current_level BETWEEN 21 AND 50 THEN '21-50'
                    ELSE '51+'
                END AS range,
                COUNT(*) AS cnt
            FROM user_xp u
            JOIN user_voice_data v ON v.user_id = u.user_id
            WHERE v.is_member = TRUE
            GROUP BY 1
        """)
        level_distribution._metrics.clear()
        for row in levels:
            level_distribution.labels(range=row['range']).set(row['cnt'])

        # ── Labeled : avertissements par membre ───────────────────────────────
        warned = await db_manager.fetch("""
            SELECT v.username, w.user_id, COUNT(*) AS cnt
            FROM warn w
            JOIN user_voice_data v ON v.user_id = w.user_id
            GROUP BY v.username, w.user_id
            ORDER BY cnt DESC
        """)
        user_warn_count._metrics.clear()
        for row in warned:
            user_warn_count.labels(
                username=row['username'], user_id=str(row['user_id'])
            ).set(row['cnt'])

        # ── Labeled : top 15 XP ───────────────────────────────────────────────
        top_xp = await db_manager.fetch("""
            SELECT v.username, u.current_level, u.total_xp
            FROM user_xp u
            JOIN user_voice_data v ON v.user_id = u.user_id
            WHERE v.is_member = TRUE
            ORDER BY u.total_xp DESC
            LIMIT 15
        """)
        user_xp_top._metrics.clear()
        for row in top_xp:
            user_xp_top.labels(
                username=row['username'], level=str(row['current_level'])
            ).set(row['total_xp'])

        # ── Invitations ───────────────────────────────────────────────────────
        from utils.database import invite_manager
        inv_stats = await invite_manager.get_invite_stats()
        invites_total.set(inv_stats['total_codes'])
        invites_uses_total.set(inv_stats['total_uses'])
        invites_uses_7d.set(inv_stats['uses_7d'])

        top_inv = await invite_manager.get_top_inviters(limit=15)
        top_inviters._metrics.clear()
        for row in top_inv:
            top_inviters.labels(
                username=row['username'] or str(row['inviter_id']),
                user_id=str(row['inviter_id'])
            ).set(row['uses'])

        active_invites = await invite_manager.get_active_invites()
        invite_codes_list._metrics.clear()
        for row in active_invites:
            expires = row['expires_at'].strftime('%d/%m/%Y %H:%M') if row['expires_at'] else '∞'
            invite_codes_list.labels(
                code=row['code'],
                host=row['username'] or str(row['inviter_id']),
                expires_at=expires
            ).set(row['uses'])

    except Exception as e:
        logger.warning("metrics refresh error: %s", e)
