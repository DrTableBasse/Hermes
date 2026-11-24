"""Système de défis hebdomadaires."""
import logging
import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import date, time, timezone
from typing import Optional
from utils.database import quest_manager, db_manager, notification_manager
from utils.command_manager import command_enabled
from utils.decorators import administration_only
from utils.embed_style import hermes_embed, progress_bar, Colors

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
            description="Complète les défis : l'XP bonus est ajouté automatiquement !",
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
                    xp_tag = f" *(+{q['xp_reward']} XP gagnés)*"
                else:
                    xp_tag = f" · +{q['xp_reward']} XP"
                embed.add_field(
                    name=f"{status} {q['icon']} {q['title']}{xp_tag}",
                    value=f"{q['description']}\n{bar}  ·  {q['progress']}/{q['target_value']}",
                    inline=False,
                )

        await interaction.followup.send(embed=embed)

    async def notify(self, user_id: int, quest: dict):
        """Défi terminé : la récompense est versée tout de suite, sans action du membre."""
        await self.grant(user_id, quest)

    async def grant(self, user_id: int, quest: dict) -> Optional[int]:
        """Verse l'XP d'un défi terminé (une seule fois) puis prévient le membre."""
        try:
            xp = await quest_manager.claim_xp(user_id, quest['id'])
        except Exception as e:
            logger.warning("quest claim error for %s / %s: %s", user_id, quest.get('id'), e)
            return None
        if xp is None:
            return None  # déjà versée
        xp_cog = self.bot.get_cog('XPCog')
        if xp_cog:
            await xp_cog.award_xp(user_id, xp, 'quest')
        try:
            await notification_manager.create(
                user_id, 'quest_complete',
                f"Défi complété : {quest['title']}",
                f"+{xp} XP ajoutés automatiquement",
            )
        except Exception as e:
            logger.warning("notify quest error for %s: %s", user_id, e)
        await self._check_quest_achievements(user_id)
        return xp

    async def _check_quest_achievements(self, user_id: int):
        try:
            from utils.database import achievement_manager
            notifier = self.bot.get_cog('AchievementsNotifier')
            if notifier:
                total = await db_manager.fetchval(
                    "SELECT COUNT(*) FROM user_quest_progress WHERE user_id = $1 AND xp_claimed = TRUE",
                    user_id,
                ) or 0
                unlocked = await achievement_manager.check_and_unlock(
                    user_id, 'quests_completed', int(total)
                )
                for a in unlocked:
                    await notifier.notify(user_id, a['id'])
        except Exception as e:
            logger.warning(f"Quest achievement check failed: {e}")

    async def grant_pending(self) -> int:
        """Rattrapage : verse toutes les récompenses en attente (toutes semaines confondues).

        Une notification par membre, pas une par défi. Renvoie le nombre de membres crédités.
        """
        xp_cog = self.bot.get_cog('XPCog')
        count = 0
        for user_id in await quest_manager.pending_users():
            try:
                xp, n = await quest_manager.claim_all_for(user_id)
            except Exception as e:
                logger.warning("quest catch-up error for %s: %s", user_id, e)
                continue
            if not n:
                continue
            if xp_cog:
                await xp_cog.award_xp(user_id, xp, 'quest')
            try:
                label = "défi terminé" if n == 1 else "défis terminés"
                await notification_manager.create(
                    user_id, 'quest_complete',
                    "Récompenses de défis ajoutées",
                    f"+{xp} XP pour {n} {label}",
                )
            except Exception as e:
                logger.warning("notify quest catch-up error for %s: %s", user_id, e)
            await self._check_quest_achievements(user_id)
            count += 1
        return count

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
        try:
            granted = await self.grant_pending()
            if granted:
                logger.warning("Récompenses de défis rattrapées pour %s membre(s)", granted)
        except Exception as e:
            logger.warning("Rattrapage des récompenses de défis échoué : %s", e)


async def setup(bot):
    await bot.add_cog(WeeklyQuestsCog(bot))
