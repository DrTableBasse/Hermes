import os
import re
import logging
import discord
from discord.ext import commands
from utils.embed_style import hermes_embed, Colors
from utils.logging import log_role_event

logger = logging.getLogger(__name__)
BUMP_CHANNEL_ID     = int(os.getenv('BUMP_CHANNEL_ID', '1068608173310754886'))
DISBOARD_ID         = 302050872383242240
BUMP_ROLE_NAME      = os.getenv('BUMP_ROLE_NAME', 'Bumper Fou')
BUMP_ROLE_THRESHOLD = int(os.getenv('BUMP_ROLE_THRESHOLD', '20'))


def _extract_bumper_id(message: discord.Message) -> int | None:
    """Try every available Discord API surface to find who ran /bump."""
    # interaction_metadata (discord.py 2.5+ — preferred)
    meta = getattr(message, 'interaction_metadata', None)
    if meta is not None:
        user = getattr(meta, 'user', None)
        if user is not None:
            return user.id
        uid = getattr(meta, 'user_id', None)
        if uid is not None:
            return int(uid)

    # message.interaction (deprecated but still populated by some clients)
    intr = getattr(message, 'interaction', None)
    if intr is not None:
        user = getattr(intr, 'user', None)
        if user is not None:
            return user.id

    # Embed text fallback: DISBOARD embeds a <@USER_ID> mention
    if message.embeds:
        for embed in message.embeds:
            text = ' '.join(filter(None, [
                embed.description, embed.title,
                *(f.name for f in embed.fields),
                *(f.value for f in embed.fields),
            ]))
            m = re.search(r'<@!?(\d+)>', text)
            if m:
                return int(m.group(1))

    return None


class BumpTrackerCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.channel.id != BUMP_CHANNEL_ID:
            return
        if message.author.id != DISBOARD_ID:
            return

        bumper_id = _extract_bumper_id(message)
        if bumper_id is None:
            logger.warning(
                "BumpTracker: impossible de déterminer l'auteur du bump (msg %s, author %s)",
                message.id, message.author.id,
            )
            return

        from utils.database import bump_manager, quest_manager, achievement_manager, xp_manager, voice_manager

        guild = message.guild

        # Sync member into user_voice_data — required by the FK on user_bump_stats
        try:
            member = guild.get_member(bumper_id) or await guild.fetch_member(bumper_id)
        except discord.NotFound:
            logger.warning("BumpTracker: membre %s introuvable dans le serveur", bumper_id)
            return
        except Exception as e:
            logger.error("BumpTracker: fetch_member %s échoué: %s", bumper_id, e)
            return

        try:
            await voice_manager.sync_member(
                bumper_id,
                member.name,
                member.display_name,
                str(member.display_avatar.url) if member.display_avatar else None,
            )
        except Exception as e:
            logger.error("BumpTracker: sync_member %s échoué: %s", bumper_id, e)
            return

        # Increment bump count and related systems
        try:
            await bump_manager.increment(bumper_id)
            await quest_manager.update_progress(bumper_id, 'bumps', 1)
            await xp_manager.add_xp(bumper_id, xp_manager.XP_BUMP)
        except Exception as e:
            logger.error("BumpTracker: incrément bump %s échoué: %s", bumper_id, e)
            return

        new_count = await bump_manager.get_count(bumper_id)

        # Give role if threshold reached
        role_just_given = False
        if BUMP_ROLE_NAME and new_count >= BUMP_ROLE_THRESHOLD:
            role = discord.utils.get(guild.roles, name=BUMP_ROLE_NAME)
            if role and role not in member.roles:
                try:
                    await member.add_roles(role, reason=f"Bumper Fou — {new_count} bumps")
                    role_just_given = True
                    await log_role_event(self.bot, member, role, "ajouté")
                except Exception as e:
                    logger.warning("BumpTracker: impossible d'ajouter le rôle à %s: %s", bumper_id, e)

        if new_count >= BUMP_ROLE_THRESHOLD:
            progression = f"Rôle **{BUMP_ROLE_NAME}** obtenu 🎉 ({new_count} bumps au total)"
        else:
            progression = f"{new_count}/{BUMP_ROLE_THRESHOLD} vers le rôle **{BUMP_ROLE_NAME}**"

        embed = hermes_embed(title="📣 Commande /bump détectée !", color=Colors.BLUE)
        embed.add_field(name="Utilisateur",     value=member.mention,  inline=True)
        embed.add_field(name="Salon",           value=message.channel.mention, inline=True)
        embed.add_field(name="Heure",           value=discord.utils.format_dt(message.created_at, 'F'), inline=False)
        embed.add_field(name="Bumps total 🏅",  value=f"{new_count} bump{'s' if new_count != 1 else ''}", inline=True)
        embed.add_field(name="Progression 🎖️", value=progression, inline=True)
        if role_just_given:
            embed.add_field(name="🎊 Rôle obtenu", value=f"**{BUMP_ROLE_NAME}** attribué !", inline=False)
        embed.set_footer(text=f"Message DISBOARD ID : {message.id}")
        try:
            await message.channel.send(embed=embed)
        except Exception as e:
            logger.warning("BumpTracker: envoi embed échoué: %s", e)

        # Achievements
        try:
            unlocked = await achievement_manager.check_and_unlock(bumper_id, 'bumps', new_count)
            if unlocked:
                notifier = self.bot.get_cog('AchievementsNotifier')
                if notifier:
                    for a in unlocked:
                        await notifier.notify(bumper_id, a['id'])
        except Exception as e:
            logger.warning("BumpTracker: achievements check échoué pour %s: %s", bumper_id, e)


async def setup(bot: commands.Bot):
    await bot.add_cog(BumpTrackerCog(bot))
