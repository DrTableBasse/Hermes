"""Rappel en MP lorsque le bump DISBOARD est de nouveau disponible.

Le bump est enregistré par BumpTrackerCog (bump_reminder_manager.record_bump) ;
ce cog vérifie chaque minute si le délai est écoulé et prévient les inscrits.
"""
import os
import asyncio
import logging
from datetime import timedelta
from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands, tasks

from utils.database import bump_reminder_manager
from utils.command_manager import command_enabled
from utils.logging import log_command
from utils.embed_style import hermes_embed, Colors

logger = logging.getLogger(__name__)
BUMP_CHANNEL_ID = int(os.getenv('BUMP_CHANNEL_ID', '1068608173310754886'))
REMINDER_DELAY  = timedelta(minutes=int(os.getenv('BUMP_REMINDER_DELAY_MINUTES', '120')))


class BumpReminderCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.check_reminder.start()

    def cog_unload(self):
        self.check_reminder.cancel()

    # ── Commande ─────────────────────────────────────────────────────────────

    @app_commands.command(name="rappel-bump", description="Recevoir un MP quand le bump est de nouveau disponible")
    @app_commands.describe(action="Activer, désactiver ou consulter ton rappel")
    @command_enabled(guild_specific=True)
    @log_command()
    async def rappel_bump(self, interaction: discord.Interaction,
                          action: Literal["activer", "désactiver", "statut"]):
        await interaction.response.defer(ephemeral=True)
        user = interaction.user

        if action == "activer":
            if await bump_reminder_manager.is_subscribed(user.id):
                await self._reply(interaction, "🔔 Ton rappel de bump est déjà activé.", Colors.BLUE)
                return
            # Vérifie que le membre accepte les MP du bot avant de l'inscrire
            try:
                await user.send(embed=hermes_embed(
                    title="🔔  Rappel de bump activé",
                    description=(
                        f"Je t'enverrai un message ici dès que le bump sera de nouveau "
                        f"disponible dans <#{BUMP_CHANNEL_ID}>.\n\n"
                        f"Pour arrêter : `/rappel-bump désactiver`."
                    ),
                    color=Colors.GREEN,
                ))
            except discord.Forbidden:
                await self._reply(
                    interaction,
                    "❌ Je n'arrive pas à t'envoyer de message privé, le rappel n'a pas été activé.\n\n"
                    "Active les MP pour ce serveur : clic sur le nom du serveur → "
                    "**Paramètres de confidentialité** → **Messages privés**, puis relance la commande.",
                    Colors.RED,
                )
                return
            await bump_reminder_manager.subscribe(user.id)
            await self._reply(interaction, "✅ Rappel activé ! Un message de test vient de t'être envoyé en MP.",
                              Colors.GREEN)

        elif action == "désactiver":
            if await bump_reminder_manager.unsubscribe(user.id):
                await self._reply(interaction, "🔕 Rappel de bump désactivé.", Colors.GREY)
            else:
                await self._reply(interaction, "Tu n'avais pas de rappel de bump activé.", Colors.GREY)

        else:
            subscribed = await bump_reminder_manager.is_subscribed(user.id)
            lines = ["🔔 Rappel **activé**." if subscribed else "🔕 Rappel **désactivé**."]
            last_bump = await bump_reminder_manager.get_last_bump()
            if last_bump:
                next_bump = last_bump + REMINDER_DELAY
                if next_bump > discord.utils.utcnow():
                    lines.append(f"Prochain bump disponible {discord.utils.format_dt(next_bump, 'R')}.")
                else:
                    lines.append(f"Le bump est disponible maintenant dans <#{BUMP_CHANNEL_ID}> !")
            await self._reply(interaction, "\n".join(lines), Colors.BLUE)

    @staticmethod
    async def _reply(interaction: discord.Interaction, text: str, color: int):
        await interaction.followup.send(embed=hermes_embed(description=text, color=color), ephemeral=True)

    # ── Boucle de rappel ─────────────────────────────────────────────────────

    @tasks.loop(minutes=1)
    async def check_reminder(self):
        try:
            bumped_at = await bump_reminder_manager.claim_due_reminder(REMINDER_DELAY)
        except Exception as e:
            logger.error("BumpReminder: lecture de l'état échouée: %s", e)
            return
        if bumped_at is None:
            return

        subscribers = await bump_reminder_manager.get_subscribers()
        logger.info("BumpReminder: bump dispo (dernier bump %s), %d rappel(s) à envoyer",
                    bumped_at, len(subscribers))

        embed = hermes_embed(
            title="⏰  Le bump est disponible !",
            description=(
                f"Le serveur peut de nouveau être bumpé.\n"
                f"Rends-toi dans <#{BUMP_CHANNEL_ID}> et tape `/bump` 🚀"
            ),
            color=Colors.GOLD,
            footer_extra="/rappel-bump désactiver pour ne plus être prévenu",
        )
        sent = 0
        for user_id in subscribers:
            try:
                user = self.bot.get_user(user_id) or await self.bot.fetch_user(user_id)
                await user.send(embed=embed)
                sent += 1
            except (discord.Forbidden, discord.NotFound):
                # MP fermés depuis l'inscription ou compte supprimé : on désinscrit
                await bump_reminder_manager.unsubscribe(user_id)
                logger.info("BumpReminder: MP impossible pour %s, désinscription", user_id)
            except Exception as e:
                logger.warning("BumpReminder: envoi du rappel à %s échoué: %s", user_id, e)
            await asyncio.sleep(0.5)
        logger.info("BumpReminder: %d/%d rappel(s) envoyé(s)", sent, len(subscribers))

    @check_reminder.before_loop
    async def before_check_reminder(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(BumpReminderCog(bot))
