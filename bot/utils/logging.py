"""Discord embed logging utilities — styled with Hermes branding."""
import discord
import functools
import os
from dotenv import load_dotenv
from utils import settings
from utils.embed_style import hermes_embed, Colors

load_dotenv()


def _env_channel_id(env_var: str) -> int | None:
    """Journaux spécialisés hors registre (COMMAND_LOG_CHANNEL_ID, ...) : restent dans .env."""
    raw = os.getenv(env_var)
    if raw and raw.strip().isdigit():
        return int(raw.strip())
    return None


async def _log_channel(bot, setting_key: str | None = None, env_var: str | None = None):
    """Salon de journal : réglage spécialisé, sinon variable spécialisée, sinon journal général.

    Les salons réglés passent par ``ensure_channel`` (recréés s'ils ont été supprimés).
    """
    guild = bot.get_guild(int(os.getenv('GUILD_ID', '0') or '0'))
    if setting_key and settings.get(setting_key):
        return await settings.configured_channel(guild, setting_key)
    if env_var:
        ch_id = _env_channel_id(env_var)
        if ch_id:
            return bot.get_channel(ch_id)
    return await settings.configured_channel(guild, 'log_channel')


async def _send_embed(channel, embed: discord.Embed):
    if channel is None:
        return
    try:
        await channel.send(embed=embed)
    except Exception as e:
        print(f"[logging] Could not send embed to {channel.id}: {e}")


def log_command():
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(self, interaction: discord.Interaction, *args, **kwargs):
            result = await func(self, interaction, *args, **kwargs)
            try:
                cmd = getattr(interaction.command, 'name', func.__name__)
                embed = hermes_embed(
                    title="📝  Commande utilisée",
                    description=(
                        f"**Utilisateur :** {interaction.user.mention}\n"
                        f"**Commande :** `/{cmd}`\n"
                        f"**Canal :** {getattr(interaction.channel, 'mention', 'N/A')}"
                    ),
                    color=Colors.BLUE,
                    thumbnail_url=(
                        interaction.user.avatar.url
                        if interaction.user.avatar
                        else interaction.user.default_avatar.url
                    ),
                )
                await _send_embed(await _log_channel(self.bot, env_var='COMMAND_LOG_CHANNEL_ID'), embed)
            except Exception:
                pass
            return result
        return wrapper
    return decorator


async def log_admin_action(bot, action: str, moderator: discord.Member, target,
                           reason: str = None, duration: str = None):
    colors = {
        'warn': Colors.ORANGE, 'kick': Colors.RED,
        'ban': Colors.DARK_RED, 'mute': Colors.GREY,
        'tempban': Colors.DARK_RED, 'tempmute': Colors.GREY,
        'unmute': Colors.GREEN,
    }
    icons = {
        'warn': '⚠️', 'kick': '👢', 'ban': '🔨',
        'tempban': '🔨', 'tempmute': '🔇', 'mute': '🔇', 'unmute': '🔊',
    }
    embed = hermes_embed(
        title=f"{icons.get(action, '🛡️')}  {action.upper()}  ─  Log Admin",
        color=colors.get(action, Colors.BLUE),
        thumbnail_url=target.display_avatar.url if hasattr(target, 'display_avatar') else None,
    )
    embed.add_field(name="Modérateur", value=moderator.mention, inline=True)
    embed.add_field(name="Cible", value=target.mention if hasattr(target, 'mention') else str(target), inline=True)
    if duration:
        embed.add_field(name="⏱️ Durée", value=f"**{duration}**", inline=True)
    if reason:
        embed.add_field(name="📝 Raison", value=reason, inline=False)
    await _send_embed(await _log_channel(bot, setting_key='admin_log_channel'), embed)


async def log_voice_event(bot, event_type: str, user_id: int, detail: str):
    colors = {
        'voice_join': Colors.GREEN, 'voice_leave': Colors.RED, 'voice_move': Colors.ORANGE,
    }
    icons = {
        'voice_join': '🟢', 'voice_leave': '🔴', 'voice_move': '🔄',
    }
    label = event_type.replace('voice_', '').capitalize()
    embed = hermes_embed(
        title=f"{icons.get(event_type, '🎤')}  Voice {label}",
        description=f"<@{user_id}> — {detail}",
        color=colors.get(event_type, Colors.BLUE),
    )
    await _send_embed(await _log_channel(bot, setting_key='voice_log_channel'), embed)


async def log_sanction(bot, action: str, moderator: discord.Member, target, reason: str):
    embed = hermes_embed(
        title=f"⚖️  Sanction  ─  {action.upper()}",
        color=Colors.RED,
        thumbnail_url=target.display_avatar.url if hasattr(target, 'display_avatar') else None,
    )
    embed.add_field(name="Modérateur", value=moderator.mention, inline=True)
    embed.add_field(name="Cible", value=target.mention if hasattr(target, 'mention') else str(target), inline=True)
    embed.add_field(name="📝 Raison", value=reason, inline=False)
    await _send_embed(await _log_channel(bot, env_var='SANCTION_LOG_CHANNEL_ID'), embed)


async def log_confession(bot, author_id: int, content: str):
    embed = hermes_embed(
        title="🤫  Confession reçue",
        description=f">>> {content[:1000]}",
        color=Colors.PURPLE,
    )
    embed.add_field(name="Auteur (ID)", value=f"`{author_id}`", inline=True)
    await _send_embed(await _log_channel(bot, env_var='CONFESSION_LOG_CHANNEL_ID'), embed)


async def log_role_event(bot, user: discord.Member, role: discord.Role, action: str = "ajouté"):
    is_add = action == "ajouté"
    embed = hermes_embed(
        title=f"{'🏷️' if is_add else '🗑️'}  Rôle {action}",
        description=f"{user.mention} → **@{role.name}**",
        color=Colors.GREEN if is_add else Colors.GREY,
        thumbnail_url=user.display_avatar.url,
    )
    await _send_embed(await _log_channel(bot, env_var='ROLE_LOG_CHANNEL_ID'), embed)
