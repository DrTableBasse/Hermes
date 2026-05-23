"""XP et système de niveaux."""
import os
import logging
import discord
from discord import app_commands
from discord.ext import commands, tasks
from utils.database import xp_manager, db_manager, streak_manager, notification_manager, achievement_manager
from utils.command_manager import command_enabled
from utils.embed_style import hermes_embed, leaderboard_embed, progress_bar, Colors

logger = logging.getLogger(__name__)

LEVEL_ROLES: dict[int, str] = {
    5:  os.getenv('ROLE_LEVEL_5', ''),
    10: os.getenv('ROLE_LEVEL_10', ''),
    20: os.getenv('ROLE_LEVEL_20', ''),
    50: os.getenv('ROLE_LEVEL_50', ''),
}

XP_MESSAGE = xp_manager.XP_MESSAGE


class XPCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.weekly_reset.start()

    def cog_unload(self):
        self.weekly_reset.cancel()

    async def _grant_level_role(self, member: discord.Member, new_level: int):
        for threshold, role_name in sorted(LEVEL_ROLES.items()):
            if new_level >= threshold and role_name:
                role = discord.utils.get(member.guild.roles, name=role_name)
                if role and role not in member.roles:
                    try:
                        await member.add_roles(role)
                        logger.info(f"Granted level role '{role_name}' to {member.id}")
                    except discord.Forbidden:
                        pass

    async def award_xp(self, user_id: int, amount: int, source: str = '',
                        channel: discord.TextChannel | None = None):
        try:
            streak = await streak_manager.get_streak(user_id)
            multiplier = float(streak['xp_multiplier']) if streak else 1.0
            final_amount = max(1, int(amount * multiplier))

            result = await xp_manager.add_xp(user_id, final_amount)

            if result['leveled_up']:
                new_level = result['new_level']
                guild_id = int(os.getenv('GUILD_ID', '0'))
                guild = self.bot.get_guild(guild_id)
                member = guild.get_member(user_id) if guild else None

                if member and guild:
                    await self._grant_level_role(member, new_level)

                # Message dans le salon du dernier message
                if channel and member:
                    embed = hermes_embed(
                        title=f"⚡  Niveau {new_level} !",
                        description=f"Félicitations {member.mention}, tu passes au **niveau {new_level}** ! 🎉",
                        color=Colors.GOLD,
                        thumbnail_url=member.display_avatar.url,
                    )
                    embed.add_field(name="XP total", value=f"**{result['new_xp']:,}** XP", inline=True)
                    try:
                        await channel.send(embed=embed)
                    except discord.Forbidden:
                        pass

                await notification_manager.create(
                    user_id, 'level_up',
                    f"Niveau {new_level} atteint !",
                    f"Tu es passé au niveau {new_level} avec {result['new_xp']} XP totaux.",
                )

                # Débloquer et notifier les achievements de niveau en DM
                unlocked = await achievement_manager.check_and_unlock(user_id, 'level', new_level)
                if unlocked:
                    notifier = self.bot.get_cog('AchievementsNotifier')
                    if notifier:
                        for a in unlocked:
                            try:
                                await notifier.notify(user_id, a['id'])
                            except Exception as e:
                                logger.warning(f"Level achievement notify failed for {user_id}: {e}")

        except Exception as e:
            logger.error(f"award_xp error for {user_id}: {e}")

    @app_commands.command(name="level", description="Afficher votre niveau et XP")
    @command_enabled(guild_specific=True)
    async def level_cmd(self, interaction: discord.Interaction, user: discord.Member = None):
        target = user or interaction.user
        data = await xp_manager.get_user_xp(target.id)

        if not data:
            await interaction.response.send_message(
                embed=hermes_embed(description=f"❌ Aucune donnée XP pour {target.display_name}.", color=Colors.RED),
                ephemeral=True,
            )
            return

        level = data['current_level']
        xp = data['total_xp']
        next_xp = xp_manager.xp_for_level(level + 1)
        bar = progress_bar(xp, next_xp)

        embed = hermes_embed(
            title=f"⚡  Niveau {level}  ─  {target.display_name}",
            color=Colors.GOLD,
            thumbnail_url=target.display_avatar.url,
        )
        embed.add_field(name="XP Total", value=f"**{xp:,}**", inline=True)
        embed.add_field(name="Prochain niveau", value=f"**{next_xp:,}** XP", inline=True)
        embed.add_field(name="XP cette semaine", value=f"**{data['weekly_xp']:,}**", inline=True)
        embed.add_field(name="Progression", value=bar, inline=False)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="leaderboard-xp", description="Classement XP")
    @command_enabled(guild_specific=True)
    async def leaderboard_xp(self, interaction: discord.Interaction, periode: str = 'all'):
        top = await xp_manager.get_leaderboard_xp(10, periode)
        medals = {0: "🥇", 1: "🥈", 2: "🥉"}
        entries = []
        for i, row in enumerate(top):
            prefix = medals.get(i, f"`{i+1}.`")
            entries.append(f"{prefix} **{row['username']}** — Niv. {row['current_level']} · {row['period_xp']:,} XP")
        embed = leaderboard_embed("Classement XP", entries, icon="⚡")
        await interaction.response.send_message(embed=embed)

    @tasks.loop(hours=168)
    async def weekly_reset(self):
        from datetime import date
        today = date.today()
        if today.weekday() == 0:
            await db_manager.execute(
                "UPDATE user_xp SET weekly_xp = 0, week_start = $1", today
            )
            logger.info("Weekly XP reset done")


async def setup(bot):
    await bot.add_cog(XPCog(bot))
