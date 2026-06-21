import logging
import os
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands, tasks

from config import VOICE_LOG_CHANNEL_ID, VOICE_HOURS_FOR_ROLE, ROLE_BATMAN
from utils.command_manager import command_enabled
from utils.database import voice_manager, db_manager, streak_manager, quest_manager, notification_manager, achievement_manager
from utils.logging import log_voice_event
from utils.embed_style import hermes_embed, leaderboard_embed, Colors

logger = logging.getLogger(__name__)


class VoiceCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._sessions: dict[int, datetime] = {}
        self._startup_check.start()

    def cog_unload(self):
        self._startup_check.cancel()

    @tasks.loop(count=1)
    async def _startup_check(self):
        """Au démarrage, vérifie les salons vocaux déjà occupés pour Pack des Vocaux."""
        guild_id = int(os.getenv('GUILD_ID', '0'))
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return
        for channel in guild.voice_channels:
            await self._check_pack_vocaux(channel)
        logger.info("Pack des Vocaux : vérification startup terminée")

    @_startup_check.before_loop
    async def _before_startup_check(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_ready(self):
        guild_id = int(os.getenv('GUILD_ID', '0'))
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return
        now = datetime.now(timezone.utc)
        recovered = 0
        for member in guild.members:
            if member.voice and member.voice.channel and not member.bot:
                if member.id not in self._sessions:
                    self._sessions[member.id] = now
                    recovered += 1
        if recovered:
            logger.info(f"Recovered {recovered} active voice sessions on startup")

    async def _update_time(self, member: discord.Member, seconds: int, channel_id: int = None):
        try:
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            hour = now.hour
            minutes = seconds // 60

            await voice_manager.update_voice_time(member.id, member.name, seconds)

            if hour >= 22 or hour < 6:
                await db_manager.execute(
                    "UPDATE user_voice_data SET voice_night_minutes = voice_night_minutes + $2 WHERE user_id = $1",
                    member.id, minutes,
                )
            elif 6 <= hour < 9:
                await db_manager.execute(
                    "UPDATE user_voice_data SET voice_morning_minutes = voice_morning_minutes + $2 WHERE user_id = $1",
                    member.id, minutes,
                )

            if channel_id:
                await db_manager.execute("""
                    INSERT INTO user_voice_channels (user_id, channel_id, total_time, visit_count)
                    VALUES ($1, $2, $3, 1)
                    ON CONFLICT (user_id, channel_id)
                    DO UPDATE SET total_time = user_voice_channels.total_time + $3,
                                  visit_count = user_voice_channels.visit_count + 1
                """, member.id, channel_id, seconds)

                count = await db_manager.fetchval(
                    "SELECT COUNT(DISTINCT channel_id) FROM user_voice_channels WHERE user_id = $1",
                    member.id,
                )
                await db_manager.execute(
                    "UPDATE user_voice_data SET unique_voice_channels_count = $2 WHERE user_id = $1",
                    member.id, count or 0,
                )

            await db_manager.execute("""
                UPDATE user_voice_data
                SET longest_session_minutes = GREATEST(longest_session_minutes, $2),
                    total_voice_sessions = total_voice_sessions + 1,
                    last_voice_date = CURRENT_DATE
                WHERE user_id = $1
            """, member.id, minutes)

            if minutes > 0:
                xp_cog = self.bot.get_cog('XPCog')
                if xp_cog:
                    await xp_cog.award_xp(member.id, minutes, 'voice')

            await streak_manager.update_voice_streak(member.id)

            # Sync consecutive_voice_days avec le vrai streak vocal
            streak_row = await streak_manager.get_streak(member.id)
            voice_max_streak = max(
                int(streak_row.get('current_streak') or 0),
                int(streak_row.get('max_streak') or 0),
            ) if streak_row else 0
            await db_manager.execute(
                "UPDATE user_voice_data SET consecutive_voice_days = $2 WHERE user_id = $1",
                member.id, voice_max_streak,
            )

            if minutes > 0:
                completed_quests = await quest_manager.update_progress(member.id, 'voice_minutes', minutes)
                if completed_quests:
                    quest_cog = self.bot.get_cog('WeeklyQuestsCog')
                    if quest_cog:
                        for q in completed_quests:
                            await quest_cog.notify(member.id, q)

            # Fetch une seule fois pour ROLE_BATMAN et achievements
            user_data = await voice_manager.get_user(member.id)

            if ROLE_BATMAN and user_data:
                if user_data['total_time'] >= VOICE_HOURS_FOR_ROLE * 3600:
                    role = discord.utils.get(member.guild.roles, name=ROLE_BATMAN)
                    if role and role not in member.roles:
                        await member.add_roles(role)

            # Vérification achievements vocaux en temps réel (DM + rôle)
            try:
                notifier = self.bot.get_cog('AchievementsNotifier')
                if notifier and user_data:
                    for ct, val in [
                        ('voice_hours',             int((user_data['total_time'] or 0) // 3600)),
                        ('voice_night_minutes',     int(user_data.get('voice_night_minutes') or 0)),
                        ('voice_morning_minutes',   int(user_data.get('voice_morning_minutes') or 0)),
                        ('longest_session_minutes', int(user_data.get('longest_session_minutes') or 0)),
                        ('unique_voice_channels',   int(user_data.get('unique_voice_channels_count') or 0)),
                        ('consecutive_voice_days',  voice_max_streak),
                    ]:
                        unlocked = await achievement_manager.check_and_unlock(member.id, ct, val)
                        for a in unlocked:
                            await notifier.notify(member.id, a['id'])
            except Exception as e:
                logger.error(f"Voice achievement notify error for {member.id}: {e}")

        except Exception as e:
            logger.error(f"_update_time error: {e}", exc_info=True)

    async def _check_pack_vocaux(self, channel: discord.VoiceChannel):
        """Vérifie l'achievement Pack des Vocaux (3+ membres simultanément) pour tous les membres du salon."""
        human = [m for m in channel.members if not m.bot]
        if len(human) < 3:
            return
        notifier = self.bot.get_cog('AchievementsNotifier')
        if not notifier:
            return
        count = len(human)
        for m in human:
            try:
                unlocked = await achievement_manager.check_and_unlock(
                    m.id, 'max_concurrent_members', count
                )
                for a in unlocked:
                    await notifier.notify(m.id, a['id'])
            except Exception as e:
                logger.warning(f"Pack des Vocaux check failed for {m.id}: {e}")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member,
                                     before: discord.VoiceState, after: discord.VoiceState):
        if member.bot:
            return
        now = datetime.now(timezone.utc)

        joined = before.channel is None and after.channel is not None
        left   = before.channel is not None and after.channel is None
        moved  = (before.channel is not None and after.channel is not None
                  and before.channel != after.channel)

        if joined:
            self._sessions[member.id] = now
            await log_voice_event(self.bot, 'voice_join', member.id,
                                  f"Rejoint **{after.channel.name}**", VOICE_LOG_CHANNEL_ID)
            await self._check_pack_vocaux(after.channel)

        elif left:
            if member.id in self._sessions:
                secs = int((now - self._sessions.pop(member.id)).total_seconds())
                if secs > 0:
                    await self._update_time(member, secs, before.channel.id)
            await log_voice_event(self.bot, 'voice_leave', member.id,
                                  f"Quitté **{before.channel.name}**", VOICE_LOG_CHANNEL_ID)

        elif moved:
            if member.id in self._sessions:
                secs = int((now - self._sessions[member.id]).total_seconds())
                if secs > 0:
                    await self._update_time(member, secs, before.channel.id)
                self._sessions[member.id] = now
            await log_voice_event(self.bot, 'voice_move', member.id,
                                  f"**{before.channel.name}** → **{after.channel.name}**", VOICE_LOG_CHANNEL_ID)
            await self._check_pack_vocaux(after.channel)

    @app_commands.command(name="voicetime", description="Afficher le temps vocal d'un utilisateur")
    @command_enabled(guild_specific=True)
    async def voicetime(self, interaction: discord.Interaction, user: discord.Member = None):
        target = user or interaction.user
        data = await voice_manager.get_user(target.id)
        if not data:
            await interaction.response.send_message(
                embed=hermes_embed(description=f"❌ Aucune donnée vocale pour {target.display_name}.", color=Colors.RED),
                ephemeral=True,
            )
            return
        s = data['total_time']
        h, r = divmod(s, 3600)
        m, sec = divmod(r, 60)
        embed = hermes_embed(
            title=f"🎤  Temps vocal  ─  {target.display_name}",
            color=Colors.BLUE,
            thumbnail_url=target.display_avatar.url,
        )
        embed.add_field(name="⏱️ Total", value=f"**{h}**h **{m}**m **{sec}**s", inline=True)
        embed.add_field(name="📊 Sessions", value=str(data.get('total_voice_sessions', '—')), inline=True)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="voice-leaderboard", description="Classement temps vocal")
    @command_enabled(guild_specific=True)
    async def voice_leaderboard(self, interaction: discord.Interaction):
        top = await voice_manager.get_leaderboard(10)
        medals = {0: "🥇", 1: "🥈", 2: "🥉"}
        entries = []
        for i, row in enumerate(top):
            s = row['total_time']
            h, r = divmod(s, 3600)
            m, _ = divmod(r, 60)
            prefix = medals.get(i, f"`{i+1}.`")
            entries.append(f"{prefix} **{row['username']}** — {h}h {m}m")
        embed = leaderboard_embed("Classement Vocal", entries, icon="🎤")
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(VoiceCog(bot))
