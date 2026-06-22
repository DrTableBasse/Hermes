import asyncio
import logging
import os
import sys

import discord
import uvicorn
from discord.ext import commands
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
load_dotenv()

from config import validate_config, BOT_API_PORT
from utils.constants import cogs_names
from utils.database import init_database, voice_manager, message_stats_manager, db_manager, achievement_manager, command_stats_manager
from utils.command_manager import init_command_status_table
from utils.embed_style import hermes_embed, Colors

console = Console()
intents  = discord.Intents.all()
bot      = commands.Bot(command_prefix='!', intents=intents)
_first_ready = True


# ── Cog loading ───────────────────────────────────────────────────────────────

async def load_cogs():
    table = Table(title="Cogs", show_lines=True)
    table.add_column("Module", style="cyan")
    table.add_column("Statut", justify="center")
    names = cogs_names()
    ok = 0
    for cog in names:
        try:
            await bot.load_extension(cog)
            table.add_row(cog, "[green]✅")
            ok += 1
        except Exception as e:
            table.add_row(cog, f"[red]❌ {str(e)[:40]}")
            console.print(f"[red]Detail {cog}: {e}[/red]")
    console.print(table)
    console.print(f"[green]{ok}/{len(names)} cogs chargés[/green]")


# ── Events ────────────────────────────────────────────────────────────────────

@bot.event
async def on_ready():
    global _first_ready
    console.print(f"[green]✅ Connecté en tant que {bot.user}[/green]")

    # On Discord reconnects, on_ready fires again — skip full init.
    if not _first_ready:
        return
    _first_ready = False

    try:
        validate_config()
    except ValueError as e:
        console.print(f"[red]❌ Config: {e}[/red]")
        return

    GUILD_ID         = int(os.getenv('GUILD_ID'))
    BOT_CHANNEL_START = int(os.getenv('BOT_CHANNEL_START'))

    guild = bot.get_guild(GUILD_ID)
    if not guild:
        console.print("[red]❌ Serveur introuvable[/red]")
        return

    # Share bot instance with internal API
    try:
        from api import set_bot_instance
        set_bot_instance(bot)
    except Exception as e:
        console.print(f"[yellow]⚠️ API bot non disponible: {e}[/yellow]")

    # Database
    try:
        await init_database()
        await init_command_status_table()
        console.print("[green]✅ Base de données prête[/green]")
    except Exception as e:
        console.print(f"[red]❌ DB: {e}[/red]")
        return

    # Sync members — reset is_member first so leavers are marked FALSE
    try:
        await guild.chunk(cache=True)
        await voice_manager.db.execute("UPDATE user_voice_data SET is_member = FALSE")
        synced = 0
        for member in guild.members:
            if not member.bot:
                avatar = str(member.avatar.url) if member.avatar else None
                nick   = member.nick if member.nick != member.name else None
                await voice_manager.sync_member(member.id, member.name, nick, avatar)
                synced += 1
        console.print(f"[green]✅ {synced} membres synchronisés[/green]")
    except Exception as e:
        console.print(f"[yellow]⚠️ Sync membres: {e}[/yellow]")

    # Startup message
    try:
        channel = guild.get_channel(BOT_CHANNEL_START)
        if channel:
            bot_avatar = bot.user.avatar.url if bot.user.avatar else bot.user.default_avatar.url
            embed = hermes_embed(
                title="Hermes au pied ! 🐾",
                description=(
                    "Bark Bark ! Je suis prêt à servir ! 🐶"
                ),
                color=Colors.GOLD,
                thumbnail_url=bot_avatar,
                footer_extra="Développé avec ❤️ par Dr.TableBasse",
            )
            embed.add_field(name="Nom du Bot", value="Hermes", inline=False)
            embed.add_field(name="Github du Bot", value="[Github](https://github.com/drtablebasse/Hermes)", inline=False)
            await channel.send(embed=embed)
    except Exception as e:
        logger.warning(f"Impossible d'envoyer le message de démarrage: {e}")

    await load_cogs()

    # Sync slash commands
    try:
        bot.tree.copy_global_to(guild=discord.Object(id=GUILD_ID))
        await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
        console.print("[green]✅ Commandes slash synchronisées[/green]")
    except Exception as e:
        console.print(f"[red]❌ Sync commandes: {e}[/red]")


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    # Track message stats
    try:
        await message_stats_manager.increment(message.author.id, message.channel.id)
    except Exception as e:
        logger.warning(f"Erreur tracking message stats: {e}")

    await bot.process_commands(message)

    # Award XP et tracking streak/quêtes pour chaque message
    try:
        if not message.author.bot and message.guild:
            xp_cog = bot.get_cog('XPCog')
            if xp_cog:
                from cogs.gamification.xp import XP_MESSAGE
                await xp_cog.award_xp(message.author.id, XP_MESSAGE, 'message', channel=message.channel)
            from utils.database import streak_manager, quest_manager
            streak_result = await streak_manager.update_message_streak(message.author.id)
            completed = await quest_manager.update_progress(message.author.id, 'messages', 1)
            if completed:
                quest_cog = bot.get_cog('WeeklyQuestsCog')
                if quest_cog:
                    for q in completed:
                        await quest_cog.notify(message.author.id, q)

            if message.attachments:
                _image_types = ('image/', 'video/')
                _image_exts  = ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.mp4', '.mov', '.avi', '.mkv')
                has_media = any(
                    (att.content_type and any(att.content_type.startswith(t) for t in _image_types))
                    or att.filename.lower().endswith(_image_exts)
                    for att in message.attachments
                )
                if has_media:
                    completed = await quest_manager.update_progress(message.author.id, 'images_posted', 1)
                    if completed:
                        quest_cog = bot.get_cog('WeeklyQuestsCog')
                        if quest_cog:
                            for q in completed:
                                await quest_cog.notify(message.author.id, q)
            # Achievements messages en temps réel
            try:
                notifier = bot.get_cog('AchievementsNotifier')
                if notifier:
                    stats = await db_manager.fetchrow("""
                        SELECT COALESCE(SUM(message_count), 0) AS total,
                               COUNT(DISTINCT channel_id)       AS channels
                        FROM user_message_stats WHERE user_id = $1
                    """, message.author.id)
                    msg_total    = int(stats['total']    or 0) if stats else 0
                    msg_channels = int(stats['channels'] or 0) if stats else 0
                    msg_streak   = int(streak_result.get('streak') or 0) if streak_result else 0
                    for ct, val in [
                        ('messages',               msg_total),
                        ('messages_multi_channel', msg_channels),
                        ('message_streak_days',    msg_streak),
                    ]:
                        unlocked = await achievement_manager.check_and_unlock(message.author.id, ct, val)
                        for a in unlocked:
                            await notifier.notify(message.author.id, a['id'])
            except Exception as e:
                logger.warning(f"Message achievement check failed: {e}")

    except Exception as e:
        logger.warning(f"XP/streak tracking on message: {e}")


@bot.event
async def on_app_command_completion(interaction: discord.Interaction, command: discord.app_commands.Command):
    if interaction.user.bot:
        return
    try:
        await command_stats_manager.increment(interaction.user.id, command.name)
        notifier = bot.get_cog('AchievementsNotifier')
        if notifier:
            total_cmds = await db_manager.fetchval(
                "SELECT COALESCE(SUM(usage_count), 0) FROM user_command_stats WHERE user_id = $1",
                interaction.user.id,
            ) or 0
            to_check = [('commands_used', int(total_cmds))]
            if command.name in ('blague', 'confess'):
                cmd_count = await db_manager.fetchval(
                    "SELECT COALESCE(usage_count, 0) FROM user_command_stats"
                    " WHERE user_id = $1 AND command_name = $2",
                    interaction.user.id, command.name,
                ) or 0
                to_check.append((f'{command.name}_count', int(cmd_count)))
            for ct, val in to_check:
                unlocked = await achievement_manager.check_and_unlock(interaction.user.id, ct, val)
                for a in unlocked:
                    await notifier.notify(interaction.user.id, a['id'])
    except Exception as e:
        logger.warning(f"Command stats tracking: {e}")


@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    if bot.user and payload.user_id == bot.user.id:
        return
    try:
        from utils.database import quest_manager
        completed = await quest_manager.update_progress(payload.user_id, 'reactions_given', 1)
        if completed:
            quest_cog = bot.get_cog('WeeklyQuestsCog')
            if quest_cog:
                for q in completed:
                    await quest_cog.notify(payload.user_id, q)
    except Exception as e:
        logger.warning(f"Reaction quest tracking: {e}")


@bot.event
async def on_member_join(member: discord.Member):
    if member.bot:
        return
    avatar = str(member.avatar.url) if member.avatar else None
    await voice_manager.sync_member(member.id, member.name, None, avatar)


@bot.event
async def on_member_remove(member: discord.Member):
    if member.bot:
        return
    await voice_manager.mark_left(member.id)


# ── Entry point ───────────────────────────────────────────────────────────────

async def main():
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        console.print("[red]❌ DISCORD_TOKEN manquant[/red]")
        return

    from api import app as api_app
    uvicorn_config = uvicorn.Config(api_app, host="0.0.0.0", port=BOT_API_PORT, log_level="warning")
    uvicorn_server = uvicorn.Server(uvicorn_config)
    console.print(f"[green]✅ API interne démarrée sur :{BOT_API_PORT}[/green]")

    await asyncio.gather(
        bot.start(token),
        uvicorn_server.serve(),
    )


if __name__ == '__main__':
    asyncio.run(main())
