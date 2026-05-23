"""Centralized embed styling for Hermes bot — consistent branding across all commands and logs."""
import discord
from datetime import datetime


# ── Brand Colors ──────────────────────────────────────────────────────────

class Colors:
    GOLD     = 0xF5A623
    BLUE     = 0x5865F2
    GREEN    = 0x57F287
    RED      = 0xED4245
    ORANGE   = 0xFF9B50
    PURPLE   = 0x9B59B6
    DARK_RED = 0xA12D2F
    GREY     = 0x95A5A6
    YELLOW   = 0xFEE75C
    DARK     = 0x2B2D31


FOOTER_TEXT = "Hermes · SaucisseLand"


def hermes_embed(
    *,
    title: str = None,
    description: str = None,
    color: int = Colors.BLUE,
    thumbnail_url: str = None,
    image_url: str = None,
    footer_extra: str = None,
) -> discord.Embed:
    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=datetime.now(),
    )
    if thumbnail_url:
        embed.set_thumbnail(url=thumbnail_url)
    if image_url:
        embed.set_image(url=image_url)
    footer = FOOTER_TEXT
    if footer_extra:
        footer = f"{footer_extra}  ·  {footer}"
    embed.set_footer(text=footer)
    return embed


def moderation_embed(
    action: str,
    moderator: discord.Member,
    target: discord.Member | discord.User,
    reason: str = None,
    duration: str = None,
) -> discord.Embed:
    colors = {
        'warn': Colors.ORANGE, 'kick': Colors.RED, 'ban': Colors.DARK_RED,
        'tempban': Colors.DARK_RED, 'tempmute': Colors.GREY,
        'mute': Colors.GREY, 'unmute': Colors.GREEN,
    }
    icons = {
        'warn': '⚠️', 'kick': '👢', 'ban': '🔨',
        'tempban': '🔨', 'tempmute': '🔇', 'mute': '🔇', 'unmute': '🔊',
    }
    embed = hermes_embed(
        title=f"{icons.get(action, '🛡️')}  {action.replace('_', ' ').upper()}",
        color=colors.get(action, Colors.BLUE),
        thumbnail_url=target.display_avatar.url,
    )
    embed.add_field(name="Cible", value=f"{target.mention}\n`ID: {target.id}`", inline=True)
    embed.add_field(name="Modérateur", value=moderator.mention, inline=True)
    if duration:
        embed.add_field(name="⏱️ Durée", value=f"**{duration}**", inline=True)
    if reason:
        embed.add_field(name="📝 Raison", value=reason, inline=False)
    return embed


async def send_sanction_dm(
    user: discord.Member | discord.User,
    action: str,
    reason: str,
    guild_name: str,
    guild_icon_url: str | None = None,
    moderator_name: str | None = None,
    duration: str | None = None,
) -> None:
    """Send a sanction notification embed as DM. Silently ignores Forbidden."""
    _labels = {
        'warn':     ('⚠️',  'Avertissement',           Colors.ORANGE),
        'kick':     ('👢',  'Expulsion',                Colors.RED),
        'ban':      ('🔨',  'Bannissement',             Colors.DARK_RED),
        'tempban':  ('🔨',  'Bannissement temporaire',  Colors.DARK_RED),
        'tempmute': ('🔇',  'Mise en sourdine',         Colors.GREY),
        'timeout':  ('🔇',  'Mise en sourdine',         Colors.GREY),
    }
    icon_str, label, color = _labels.get(action, ('🛡️', action.upper(), Colors.BLUE))
    embed = hermes_embed(
        title=f"{icon_str}  {label}",
        description=f"Vous avez reçu une sanction sur **{guild_name}**.",
        color=color,
        thumbnail_url=guild_icon_url,
    )
    embed.add_field(name="📝 Raison", value=reason, inline=False)
    if moderator_name:
        embed.add_field(name="👮 Modérateur", value=moderator_name, inline=True)
    if duration:
        embed.add_field(name="⏱️ Durée", value=duration, inline=True)
    try:
        await user.send(embed=embed)
    except (discord.Forbidden, discord.NotFound, discord.HTTPException):
        pass


def leaderboard_embed(title: str, entries: list[str], *, icon: str = "🏆") -> discord.Embed:
    embed = hermes_embed(
        title=f"{icon}  {title}",
        description="\n".join(entries) if entries else "*Aucune donnée*",
        color=Colors.GOLD,
    )
    return embed


def profile_field(name: str, value, *, inline: bool = True):
    return {"name": name, "value": str(value), "inline": inline}


def progress_bar(current: int, total: int, *, length: int = 10) -> str:
    if total <= 0:
        pct = 100
    else:
        pct = min(100, int((current / total) * 100))
    filled = pct * length // 100
    return f"`{'█' * filled}{'░' * (length - filled)}` {pct}%"
