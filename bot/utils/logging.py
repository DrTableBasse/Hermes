"""Discord embed logging utilities."""
import discord
import functools
import os
from datetime import datetime
from dotenv import load_dotenv

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
                cmd   = getattr(interaction.command, 'name', func.__name__)
                embed = discord.Embed(
                    title="📝 Commande utilisée",
                    description=f"{interaction.user.mention} → `/{cmd}`",
                    color=discord.Color.blue(),
                    timestamp=datetime.now(),
                )
                embed.set_thumbnail(
                    url=interaction.user.avatar.url if interaction.user.avatar else interaction.user.default_avatar.url
                )
                embed.add_field(name="Canal", value=getattr(interaction.channel, 'mention', 'N/A'), inline=True)
                await _send_embed(self.bot, ch_id, embed)
            except Exception:
                pass
            return result
        return wrapper
    return decorator


async def log_admin_action(bot, action: str, moderator: discord.Member, target: discord.Member,
                            reason: str = None, duration: str = None):
    ch_id = _get_channel_id('ADMIN_LOG_CHANNEL_ID')
    colors = {
        'warn': discord.Color.orange(), 'kick': discord.Color.red(),
        'ban': discord.Color.dark_red(), 'mute': discord.Color.greyple(),
        'tempban': discord.Color.dark_orange(), 'tempmute': discord.Color.greyple(),
        'unmute': discord.Color.green(),
    }
    embed = discord.Embed(
        title=f"🛡️ {action.upper()}",
        color=colors.get(action, discord.Color.blurple()),
        timestamp=datetime.now(),
    )
    embed.add_field(name="Modérateur", value=moderator.mention, inline=True)
    embed.add_field(name="Cible",      value=target.mention,    inline=True)
    if reason:
        embed.add_field(name="Raison", value=reason, inline=False)
    if duration:
        embed.add_field(name="Durée", value=duration, inline=True)
    await _send_embed(bot, ch_id, embed)


async def log_voice_event(bot, event_type: str, user_id: int, detail: str, channel_id: int | None):
    ch_id = channel_id or _get_channel_id('VOICE_LOG_CHANNEL_ID')
    colors = {'voice_join': discord.Color.green(), 'voice_leave': discord.Color.red(),
               'voice_move': discord.Color.orange()}
    embed = discord.Embed(
        title=f"🎤 {event_type.replace('_', ' ').title()}",
        description=f"<@{user_id}> — {detail}",
        color=colors.get(event_type, discord.Color.blue()),
        timestamp=datetime.now(),
    )
    await _send_embed(bot, ch_id, embed)


async def log_sanction(bot, action: str, moderator: discord.Member, target: discord.Member, reason: str):
    ch_id = _get_channel_id('SANCTION_LOG_CHANNEL_ID')
    embed = discord.Embed(
        title=f"⚖️ Sanction — {action.upper()}",
        color=discord.Color.red(),
        timestamp=datetime.now(),
    )
    embed.add_field(name="Modérateur", value=moderator.mention, inline=True)
    embed.add_field(name="Cible",      value=target.mention,    inline=True)
    embed.add_field(name="Raison",     value=reason,            inline=False)
    await _send_embed(bot, ch_id, embed)


async def log_confession(bot, author_id: int, content: str):
    ch_id = _get_channel_id('CONFESSION_LOG_CHANNEL_ID')
    embed = discord.Embed(
        title="🤫 Confession reçue",
        description=content[:1000],
        color=discord.Color.purple(),
        timestamp=datetime.now(),
    )
    embed.add_field(name="Auteur (ID)", value=str(author_id), inline=True)
    await _send_embed(bot, ch_id, embed)
