"""Commande d'audit admin — profil complet d'un membre."""
import logging
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

from utils.database import (
    voice_manager, message_stats_manager, xp_manager,
    db_manager, bump_manager, invite_manager,
)
from utils.decorators import administration_only
from utils.embed_style import hermes_embed, Colors

logger = logging.getLogger(__name__)

ACTION_ICONS = {
    'warn':     '⚠️',
    'kick':     '👢',
    'tempban':  '🔨',
    'ban':      '🔨',
    'tempmute': '🔇',
    'mute':     '🔇',
    'unmute':   '🔊',
}


class AuditCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="audit", description="Profil d'audit complet d'un membre (admin)")
    @administration_only()
    async def audit(self, interaction: discord.Interaction, user: discord.Member):
        await interaction.response.defer(ephemeral=True)

        voice_data, total_msgs, xp_data, bumps, invites = await _gather(
            voice_manager.get_user(user.id),
            message_stats_manager.get_total(user.id),
            xp_manager.get_user_xp(user.id),
            bump_manager.get_count(user.id),
            invite_manager.get_count(user.id),
        )
        warn_count, ach_count, recent_warns, recent_actions, last_cmd = await _gather(
            db_manager.fetchval("SELECT COUNT(*) FROM warn WHERE user_id = $1", user.id),
            db_manager.fetchval("SELECT COUNT(*) FROM user_achievements WHERE user_id = $1", user.id),
            db_manager.fetch(
                "SELECT reason, create_time, moderator_id FROM warn WHERE user_id = $1 ORDER BY create_time DESC LIMIT 3",
                user.id,
            ),
            db_manager.fetch(
                "SELECT action_type, actor_name, details, created_at FROM admin_logs WHERE target_id = $1 ORDER BY created_at DESC LIMIT 5",
                user.id,
            ),
            db_manager.fetchrow(
                "SELECT command_name, last_used FROM user_command_stats WHERE user_id = $1 ORDER BY last_used DESC LIMIT 1",
                user.id,
            ),
        )

        embed = hermes_embed(
            title=f"🔍  Audit — {user.display_name}",
            color=Colors.PURPLE,
            thumbnail_url=user.display_avatar.url,
        )

        # ── Identité ──────────────────────────────────────────────────────
        created_ts = int(user.created_at.timestamp())
        joined_ts  = int(user.joined_at.timestamp()) if user.joined_at else None

        id_lines = [
            f"Compte créé : <t:{created_ts}:R>",
            f"Arrivé sur le serveur : <t:{joined_ts}:R>" if joined_ts else "Date d'arrivée inconnue",
            f"ID : `{user.id}`",
        ]
        embed.add_field(name="👤 Identité", value="\n".join(id_lines), inline=False)

        # Rôles (sans @everyone)
        roles = [r.mention for r in reversed(user.roles) if r.name != "@everyone"]
        embed.add_field(
            name=f"🏷️ Rôles ({len(roles)})",
            value=" ".join(roles[:10]) if roles else "*Aucun rôle*",
            inline=False,
        )

        # ── Activité serveur ──────────────────────────────────────────────
        s = voice_data['total_time'] if voice_data else 0
        h, rem = divmod(s, 3600)
        m, _ = divmod(rem, 60)

        level = xp_data['current_level'] if xp_data else 1
        xp    = xp_data['total_xp'] if xp_data else 0

        warn_color = "🔴" if (warn_count or 0) >= 3 else "🟡" if (warn_count or 0) >= 1 else "🟢"

        stats_lines = [
            f"🎤 Vocal : **{h}h {m}m**",
            f"💬 Messages : **{total_msgs:,}**",
            f"⚡ Niveau **{level}** · {xp:,} XP",
            f"{warn_color} Avertissements : **{warn_count or 0}**",
            f"🏆 Achievements : **{ach_count or 0}**",
            f"🔔 Bumps : **{bumps}**  ·  📨 Invitations : **{invites}**",
        ]
        embed.add_field(name="📊 Activité", value="\n".join(stats_lines), inline=False)

        # ── Dernière activité connue ───────────────────────────────────────
        activity_lines = []
        if voice_data and voice_data.get('last_seen'):
            last_seen_ts = int(voice_data['last_seen'].timestamp())
            activity_lines.append(f"🎤 Dernière activité vocal : <t:{last_seen_ts}:R>")
        if last_cmd:
            cmd_ts = int(last_cmd['last_used'].timestamp())
            activity_lines.append(f"⌨️ Dernière commande : `/{last_cmd['command_name']}` <t:{cmd_ts}:R>")
        if activity_lines:
            embed.add_field(name="🕐 Dernière activité", value="\n".join(activity_lines), inline=False)

        # ── Sanctions récentes ────────────────────────────────────────────
        if recent_warns:
            warn_lines = []
            for w in recent_warns:
                mod = f"<@{w['moderator_id']}>" if w.get('moderator_id') else "?"
                warn_lines.append(f"⚠️ <t:{w['create_time']}:R> — {w['reason'][:60]} · par {mod}")
            embed.add_field(name="⚠️ Sanctions récentes", value="\n".join(warn_lines), inline=False)

        # ── Historique admin ──────────────────────────────────────────────
        if recent_actions:
            action_lines = []
            for a in recent_actions:
                icon = ACTION_ICONS.get(a['action_type'], '🛡️')
                ts   = int(a['created_at'].timestamp())
                actor = a['actor_name'] or '?'
                action_lines.append(f"{icon} <t:{ts}:R> — `{a['action_type']}` par **{actor}**")
            embed.add_field(name="🛡️ Historique admin", value="\n".join(action_lines), inline=False)

        embed.set_footer(text=f"Audit confidentiel  ·  Hermes · SaucisseLand")
        await interaction.followup.send(embed=embed, ephemeral=True)


async def _gather(*coros):
    import asyncio
    return await asyncio.gather(*coros)


async def setup(bot):
    await bot.add_cog(AuditCog(bot))
