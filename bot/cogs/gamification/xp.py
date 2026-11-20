"""XP et système de niveaux."""
import os
import logging
import discord
from discord import app_commands
from discord.ext import commands, tasks
from utils.database import xp_manager, db_manager, streak_manager, notification_manager, achievement_manager
from utils import settings
from utils.command_manager import command_enabled
from utils.grades import grade_for_level, next_grade, load_grades, color_to_int, progress
from utils.embed_style import hermes_embed, leaderboard_embed, progress_bar, Colors

logger = logging.getLogger(__name__)

# niveau -> clé du réglage (rôle stocké par identifiant, lu à l'usage)
LEVEL_ROLE_KEYS: dict[int, str] = {
    5:  'role_level_5',
    10: 'role_level_10',
    20: 'role_level_20',
    50: 'role_level_50',
}

XP_MESSAGE = xp_manager.XP_MESSAGE


class XPCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.weekly_reset.start()

    def cog_unload(self):
        self.weekly_reset.cancel()

    async def _grant_level_role(self, member: discord.Member, new_level: int):
        for threshold, key in sorted(LEVEL_ROLE_KEYS.items()):
            if new_level >= threshold:
                role = settings.get_role(member.guild, key)
                if role and role not in member.roles:
                    try:
                        await member.add_roles(role)
                        logger.info(f"Granted level role '{role.name}' to {member.id}")
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

        level = data['current_level'] or 1
        xp = data['total_xp']
        _, _, next_xp, ratio = progress(xp)
        bar = progress_bar(int(ratio * 100), 100)

        embed = hermes_embed(
            title=f"⚡  Niveau {level}  ─  {target.display_name}",
            color=Colors.GOLD,
            thumbnail_url=target.display_avatar.url,
        )
        grade = grade_for_level(level, await load_grades(db_manager))
        embed.add_field(name="Grade", value=f"**{grade['name']}**", inline=False)
        embed.add_field(name="XP Total", value=f"**{xp:,}**", inline=True)
        embed.add_field(name="Prochain niveau", value=f"**{next_xp:,}** XP", inline=True)
        embed.add_field(name="XP cette semaine", value=f"**{data['weekly_xp']:,}**", inline=True)
        embed.add_field(name="Progression", value=bar, inline=False)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="rang", description="Afficher votre grade charcutier")
    @command_enabled(guild_specific=True)
    async def rang_cmd(self, interaction: discord.Interaction, membre: discord.Member = None):
        target = membre or interaction.user
        data = await xp_manager.get_user_xp(target.id)

        if not data:
            await interaction.response.send_message(
                embed=hermes_embed(description=f"❌ Aucune donnée XP pour {target.display_name}.", color=Colors.RED),
                ephemeral=True,
            )
            return

        level = data['current_level'] or 1
        xp = data['total_xp']
        grades = await load_grades(db_manager)
        grade = grade_for_level(level, grades)
        upcoming = next_grade(level, grades)

        _, _, _, ratio = progress(xp)
        bar = progress_bar(int(ratio * 100), 100)

        embed = hermes_embed(
            title=f"🥩  {grade['name']}  ─  {target.display_name}",
            color=color_to_int(grade['color']),
            thumbnail_url=target.display_avatar.url,
            footer_extra="Hermes a vérifié. Deux fois.",
        )
        embed.add_field(name="Niveau", value=f"**{level}**", inline=True)
        embed.add_field(name="XP Total", value=f"**{xp:,}**", inline=True)
        if upcoming:
            embed.add_field(
                name="Prochain grade",
                value=f"**{upcoming['name']}** au niveau **{upcoming['level_min']}**",
                inline=False,
            )
        else:
            embed.add_field(name="Prochain grade", value="Aucun. Tu as atteint le sommet de la charcuterie.", inline=False)
        embed.add_field(name=f"Progression vers le niveau {level + 1}", value=bar, inline=False)

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
