"""Système de défis hebdomadaires."""
import logging
import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import date, datetime, time, timezone
from utils.database import quest_manager, db_manager, notification_manager
from utils.command_manager import command_enabled
from utils.decorators import administration_only
from utils.embed_style import hermes_embed, progress_bar, Colors, FOOTER_TEXT

logger = logging.getLogger(__name__)


class WeeklyQuestsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.weekly_quest_reset.start()

    def cog_unload(self):
        self.weekly_quest_reset.cancel()

    @app_commands.command(name="quests", description="Afficher vos défis hebdomadaires")
    @command_enabled(guild_specific=True)
    async def quests_cmd(self, interaction: discord.Interaction):
        await interaction.response.defer()
        progress_list = await quest_manager.get_user_progress(interaction.user.id)

        embed = hermes_embed(
            title="📋  Défis de la semaine",
            description="Complète les défis pour gagner de l'XP bonus !",
            color=Colors.BLUE,
        )

        if not progress_list:
            embed.description = "*Aucun défi actif cette semaine.*"
        else:
            completed = sum(1 for q in progress_list if q['completed'])
            embed.description = f"**{completed}/{len(progress_list)}** défis complétés"

            for q in progress_list:
                bar = progress_bar(q['progress'], q['target_value'], length=8)
                status = "✅" if q['completed'] else "⏳"
                if q['xp_claimed']:
                    xp_tag = " *(XP réclamé)*"
                elif q['completed']:
                    xp_tag = f" **(+{q['xp_reward']} XP)**"
                else:
                    xp_tag = ""
                embed.add_field(
                    name=f"{status} {q['icon']} {q['title']}{xp_tag}",
                    value=f"{q['description']}\n{bar}  ·  {q['progress']}/{q['target_value']}",
                    inline=False,
                )

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="quest-claim", description="Réclamer l'XP d'un défi complété")
    @command_enabled(guild_specific=True)
    async def quest_claim(self, interaction: discord.Interaction, quest_id: int):
        xp = await quest_manager.claim_xp(interaction.user.id, quest_id)
        if xp is None:
            await interaction.response.send_message(
                embed=hermes_embed(
                    description="❌ Ce défi n'est pas disponible, pas encore complété, ou déjà réclamé.",
                    color=Colors.RED,
                ),
                ephemeral=True,
            )
            return
        xp_cog = self.bot.get_cog('XPCog')
        if xp_cog:
            await xp_cog.award_xp(interaction.user.id, xp, 'quest')
        await interaction.response.send_message(
            embed=hermes_embed(
                description=f"✅ **+{xp} XP** réclamés pour ce défi !",
                color=Colors.GREEN,
            ),
            ephemeral=True,
        )
        # Achievement quests_completed
        try:
            from utils.database import achievement_manager, db_manager
            notifier = self.bot.get_cog('AchievementsNotifier')
            if notifier:
                total = await db_manager.fetchval(
                    "SELECT COUNT(*) FROM user_quest_progress WHERE user_id = $1 AND xp_claimed = TRUE",
                    interaction.user.id,
                ) or 0
                unlocked = await achievement_manager.check_and_unlock(
                    interaction.user.id, 'quests_completed', int(total)
                )
                for a in unlocked:
                    await notifier.notify(interaction.user.id, a['id'])
        except Exception as e:
            logger.warning(f"Quest achievement check failed: {e}")

    async def notify(self, user_id: int, quest: dict):
        try:
            embed = discord.Embed(
                title=f"{quest['icon']}  Défi complété !",
                description=f"**{quest['title']}**\n{quest.get('description', '')}",
                color=Colors.GREEN,
                timestamp=datetime.now(),
            )
            embed.add_field(name="🎁 Récompense", value=f"**+{quest['xp_reward']} XP**", inline=True)
            embed.add_field(name="📋 Réclamer", value=f"`/quest-claim {quest['id']}`", inline=True)
            embed.set_footer(text=FOOTER_TEXT)

            discord_user = self.bot.get_user(user_id) or await self.bot.fetch_user(user_id)
            try:
                await discord_user.send(embed=embed)
            except discord.Forbidden:
                pass

            await notification_manager.create(
                user_id, 'quest_complete',
                f"Défi complété : {quest['title']}",
                f"+{quest['xp_reward']} XP disponibles — /quest-claim {quest['id']}",
            )
        except Exception as e:
            logger.warning("notify quest error for %s: %s", user_id, e)

    @app_commands.command(name="reset-quests", description="[Admin] Réinitialiser les quêtes de la semaine")
    @administration_only()
    async def reset_quests_cmd(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await db_manager.execute("UPDATE weekly_quests SET is_active = FALSE WHERE is_active = TRUE")
        await quest_manager.create_weekly_quests(force=True)
        new_quests = await quest_manager.get_active_quests()

        embed = hermes_embed(
            title="🔄  Quêtes réinitialisées",
            description=f"**{len(new_quests)}** nouvelles quêtes créées pour cette semaine.",
            color=Colors.GREEN,
        )
        for q in new_quests:
            embed.add_field(
                name=f"{q['icon']} {q['title']}",
                value=f"{q.get('description', '')} · **+{q['xp_reward']} XP**",
                inline=False,
            )
        await interaction.followup.send(embed=embed, ephemeral=True)
        logger.info("Weekly quests manually reset by %s", interaction.user)

    @tasks.loop(time=time(0, 0, tzinfo=timezone.utc))
    async def weekly_quest_reset(self):
        today = date.today()
        if today.weekday() == 0:
            await db_manager.execute(
                "UPDATE weekly_quests SET is_active = FALSE WHERE week_end < $1", today
            )
            await quest_manager.create_weekly_quests()
            logger.info("Weekly quests reset and created")

    @weekly_quest_reset.before_loop
    async def before_quest_reset(self):
        await self.bot.wait_until_ready()
        # Create quests for the current week if none exist yet
        await quest_manager.create_weekly_quests()
        logger.info("Weekly quests initialized on startup")


async def setup(bot):
    await bot.add_cog(WeeklyQuestsCog(bot))
