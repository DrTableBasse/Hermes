import logging
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

from config import VOICE_LOG_CHANNEL_ID, VOICE_HOURS_FOR_ROLE, ROLE_BATMAN
from utils.command_manager import command_enabled
from utils.database import voice_manager
from utils.logging import log_voice_event

logger = logging.getLogger(__name__)


class VoiceCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._sessions: dict[int, datetime] = {}

    async def _update_time(self, member: discord.Member, seconds: int):
        try:
            await voice_manager.update_voice_time(member.id, member.name, seconds)

            # Award role if threshold reached
            if ROLE_BATMAN:
                data = await voice_manager.get_user(member.id)
                if data and data['total_time'] >= VOICE_HOURS_FOR_ROLE * 3600:
                    role = discord.utils.get(member.guild.roles, name=ROLE_BATMAN)
                    if role and role not in member.roles:
                        await member.add_roles(role)
        except Exception as e:
            logger.error(f"_update_time: {e}")

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
                                  f"Rejoint {after.channel.name}", VOICE_LOG_CHANNEL_ID)

        elif left:
            if member.id in self._sessions:
                secs = int((now - self._sessions.pop(member.id)).total_seconds())
                if secs > 0:
                    await self._update_time(member, secs)
            await log_voice_event(self.bot, 'voice_leave', member.id,
                                  f"Quitté {before.channel.name}", VOICE_LOG_CHANNEL_ID)

        elif moved:
            if member.id in self._sessions:
                secs = int((now - self._sessions[member.id]).total_seconds())
                if secs > 0:
                    await self._update_time(member, secs)
                self._sessions[member.id] = now
            await log_voice_event(self.bot, 'voice_move', member.id,
                                  f"{before.channel.name} → {after.channel.name}", VOICE_LOG_CHANNEL_ID)

    @app_commands.command(name="voicetime", description="Afficher le temps vocal d'un utilisateur")
    @command_enabled(guild_specific=True)
    async def voicetime(self, interaction: discord.Interaction, user: discord.Member = None):
        target = user or interaction.user
        data   = await voice_manager.get_user(target.id)
        if not data:
            await interaction.response.send_message(f"❌ Aucune donnée pour {target.display_name}.", ephemeral=True)
            return
        s = data['total_time']
        h, r = divmod(s, 3600)
        m, s = divmod(r, 60)
        embed = discord.Embed(title=f"🎤 Temps vocal — {target.display_name}", color=discord.Color.blue())
        embed.add_field(name="Total", value=f"{h}h {m}m {s}s")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="voice-leaderboard", description="Classement temps vocal")
    async def voice_leaderboard(self, interaction: discord.Interaction):
        top = await voice_manager.get_leaderboard(10)
        embed = discord.Embed(title="🏆 Classement Vocal", color=discord.Color.gold())
        for i, row in enumerate(top, 1):
            s = row['total_time']
            h, r = divmod(s, 3600)
            m, _ = divmod(r, 60)
            medals = {1: "🥇", 2: "🥈", 3: "🥉"}
            prefix = medals.get(i, f"**{i}.**")
            embed.add_field(name=f"{prefix} {row['username']}", value=f"{h}h {m}m", inline=False)
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(VoiceCog(bot))
