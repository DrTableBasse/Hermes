import logging
import discord
from discord.ext import commands

logger = logging.getLogger(__name__)


class InviteTrackerCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # guild_id -> {invite_code: uses}
        self._cache: dict[int, dict[str, int]] = {}

    @commands.Cog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            await self._refresh_cache(guild)

    async def _refresh_cache(self, guild: discord.Guild):
        try:
            invites = await guild.invites()
            self._cache[guild.id] = {inv.code: inv.uses or 0 for inv in invites}
            from utils.database import invite_manager
            await invite_manager.sync_all_invites(invites)
        except Exception as e:
            logger.warning(f"Cannot fetch invites for guild {guild.id}: {e}")

    @commands.Cog.listener()
    async def on_invite_create(self, invite: discord.Invite):
        if not invite.guild:
            return
        self._cache.setdefault(invite.guild.id, {})[invite.code] = invite.uses or 0
        if invite.inviter and not invite.inviter.bot:
            from utils.database import invite_manager
            await invite_manager.upsert_invite(
                code=invite.code,
                inviter_id=invite.inviter.id,
                uses=invite.uses or 0,
                max_uses=invite.max_uses or None,
                expires_at=invite.expires_at,
            )

    @commands.Cog.listener()
    async def on_invite_delete(self, invite: discord.Invite):
        if not invite.guild:
            return
        self._cache.get(invite.guild.id, {}).pop(invite.code, None)
        from utils.database import invite_manager
        await invite_manager.deactivate_invite(invite.code)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot:
            return
        guild = member.guild
        used_invite: discord.Invite | None = None

        try:
            current_invites = await guild.invites()
            old_cache = self._cache.get(guild.id, {})

            for inv in current_invites:
                old_uses = old_cache.get(inv.code, 0)
                if inv.uses > old_uses and inv.inviter and not inv.inviter.bot:
                    used_invite = inv
                    break

            self._cache[guild.id] = {inv.code: inv.uses or 0 for inv in current_invites}
        except Exception as e:
            logger.warning(f"Cannot fetch invites on member join: {e}")

        self.bot.dispatch('member_join_tracked', member, used_invite)

        if used_invite is None:
            return

        inviter_id = used_invite.inviter.id
        from utils.database import invite_manager, quest_manager, achievement_manager
        await invite_manager.increment(inviter_id)
        await invite_manager.record_use(used_invite.code, inviter_id, member.id)
        completed_quests = await quest_manager.update_progress(inviter_id, 'invites', 1)
        if completed_quests:
            quest_cog = self.bot.get_cog('WeeklyQuestsCog')
            if quest_cog:
                for q in completed_quests:
                    await quest_cog.notify(inviter_id, q)

        new_count = await invite_manager.get_count(inviter_id)
        unlocked = await achievement_manager.check_and_unlock(inviter_id, 'invites', new_count)

        if unlocked:
            notifier = self.bot.get_cog('AchievementsNotifier')
            if notifier:
                for a in unlocked:
                    try:
                        await notifier.notify(inviter_id, a['id'])
                    except Exception as e:
                        logger.warning(f"Achievement notify failed for {inviter_id}: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(InviteTrackerCog(bot))
