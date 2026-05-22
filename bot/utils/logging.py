"""Discord embed logging utilities — styled with Hermes branding."""
import discord
import functools
import os
from dotenv import load_dotenv
from utils.embed_style import hermes_embed, Colors

load_dotenv()


def _get_channel_id(env_var: str, fallback: str = 'LOG_CHANNEL_ID') -> int | None:
    raw = os.getenv(env_var) or os.getenv(fallback)
    if raw and raw.strip().isdigit():
        return int(raw.strip())
    return None


async def _send_embed(bot, channel_id: int | None, embed: discord.Embed):
    if not channel_id:
        return
    try:
        channel = bot.get_channel(channel_id)
        if channel:
            await channel.send(embed=embed)
    except Exception as e:
        print(f"[logging] Could not send embed to {channel_id}: {e}")


def log_command():
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(self, interaction: discord.Interaction, *args, **kwargs):
            result = await func(self, interaction, *args, **kwargs)
            try:
                ch_id = _get_channel_id('COMMAND_LOG_CHANNEL_ID')
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
                await _send_embed(self.bot, ch_id, embed)
            except Exception:
                pass
            return result
        return wrapper
    return decorator


async def log_admin_action(bot, action: str, moderator: discord.Member, target,
                           reason: str = None, duration: str = None):
    ch_id = _get_channel_id('ADMIN_LOG_CHANNEL_ID')
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
    await _send_embed(bot, ch_id, embed)


async def log_voice_event(bot, event_type: str, user_id: int, detail: str, channel_id: int | None):
    ch_id = channel_id or _get_channel_id('VOICE_LOG_CHANNEL_ID')
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
    await _send_embed(bot, ch_id, embed)


async def log_sanction(bot, action: str, moderator: discord.Member, target, reason: str):
    ch_id = _get_channel_id('SANCTION_LOG_CHANNEL_ID')
    embed = hermes_embed(
        title=f"⚖️  Sanction  ─  {action.upper()}",
        color=Colors.RED,
        thumbnail_url=target.display_avatar.url if hasattr(target, 'display_avatar') else None,
    )
    embed.add_field(name="Modérateur", value=moderator.mention, inline=True)
    embed.add_field(name="Cible", value=target.mention if hasattr(target, 'mention') else str(target), inline=True)
    embed.add_field(name="📝 Raison", value=reason, inline=False)
    await _send_embed(bot, ch_id, embed)


async def log_confession(bot, author_id: int, content: str):
    ch_id = _get_channel_id('CONFESSION_LOG_CHANNEL_ID')
    embed = hermes_embed(
        title="🤫  Confession reçue",
        description=f">>> {content[:1000]}",
        color=Colors.PURPLE,
    )
    embed.add_field(name="Auteur (ID)", value=f"`{author_id}`", inline=True)
    await _send_embed(bot, ch_id, embed)


async def log_role_event(bot, user: discord.Member, role: discord.Role, action: str = "ajouté"):
    ch_id = _get_channel_id('ROLE_LOG_CHANNEL_ID')
    is_add = action == "ajouté"
    embed = hermes_embed(
        title=f"{'🏷️' if is_add else '🗑️'}  Rôle {action}",
        description=f"{user.mention} → **@{role.name}**",
        color=Colors.GREEN if is_add else Colors.GREY,
        thumbnail_url=user.display_avatar.url,
    )
    await _send_embed(bot, ch_id, embed)
