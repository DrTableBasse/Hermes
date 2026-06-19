"""Internal Bot API — only reachable from the Docker network (web-api calls it)."""
import asyncio
import functools
import os
from datetime import datetime, timezone, timedelta
from typing import Optional

import discord
import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Security
from fastapi.responses import Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel

from config import BOT_API_PORT, BOT_API_TOKEN

app  = FastAPI(title="Hermes Bot Internal API", docs_url=None, redoc_url=None)
_bot: Optional[discord.Client] = None
_security = HTTPBearer()


def set_bot_instance(bot: discord.Client):
    global _bot
    _bot = bot


def _require_token(creds: HTTPAuthorizationCredentials = Security(_security)):
    if creds.credentials != BOT_API_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid token")


def _get_bot() -> discord.Client:
    if _bot is None:
        raise HTTPException(status_code=503, detail="Bot not ready")
    return _bot


def _get_guild() -> discord.Guild:
    bot  = _get_bot()
    gid  = int(os.getenv('GUILD_ID', '0'))
    guild = bot.get_guild(gid)
    if not guild:
        raise HTTPException(status_code=503, detail="Guild not found")
    return guild


# ── Models ────────────────────────────────────────────────────────────────────

class WarnRequest(BaseModel):
    user_id:      int
    reason:       str
    moderator_id: int

class ModerationRequest(BaseModel):
    user_id:      int
    reason:       str = "Aucune raison spécifiée"
    moderator_id: int

class TempModerationRequest(ModerationRequest):
    duration_minutes: int = 60

class CommandToggleRequest(BaseModel):
    command_name: str
    enabled:      bool
    guild_id:     Optional[int] = None
    moderator_id: Optional[int] = None


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    ready = _bot is not None and _bot.is_ready()
    import metrics as bot_metrics
    bot_metrics.bot_ready.set(1 if ready else 0)
    return {"status": "ok" if ready else "starting", "ready": ready}


@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


# ── Warns ─────────────────────────────────────────────────────────────────────

@app.post("/warns", dependencies=[Depends(_require_token)])
async def add_warn(req: WarnRequest):
    from utils.database import warn_manager
    from utils.embed_style import send_sanction_dm
    ok = await warn_manager.add_warn(req.user_id, req.reason, req.moderator_id)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to add warn")
    try:
        guild = _get_guild()
        target = guild.get_member(req.user_id) or await _get_bot().fetch_user(req.user_id)
        mod = guild.get_member(req.moderator_id)
        mod_name = mod.display_name if mod else f"<@{req.moderator_id}>"
        await send_sanction_dm(
            target, 'warn', req.reason,
            guild_name=guild.name,
            guild_icon_url=guild.icon.url if guild.icon else None,
            moderator_name=mod_name,
        )
    except Exception:
        pass
    return {"success": True}

@app.get("/warns/{user_id}", dependencies=[Depends(_require_token)])
async def get_warns(user_id: int):
    from utils.database import warn_manager
    warns = await warn_manager.get_user_warns(user_id)
    return {"warns": warns}

@app.delete("/warns/{warn_id}", dependencies=[Depends(_require_token)])
async def delete_warn(warn_id: int):
    from utils.database import warn_manager
    ok = await warn_manager.delete_warn(warn_id)
    return {"success": ok}

@app.put("/warns/{warn_id}", dependencies=[Depends(_require_token)])
async def update_warn(warn_id: int, reason: str):
    from utils.database import warn_manager
    ok = await warn_manager.update_reason(warn_id, reason)
    return {"success": ok}


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_member(guild: discord.Guild, user_id: int) -> discord.Member:
    member = guild.get_member(user_id)
    if member is None:
        try:
            member = await guild.fetch_member(user_id)
        except discord.NotFound:
            raise HTTPException(status_code=404, detail="Member not found")
        except discord.HTTPException as e:
            raise HTTPException(status_code=502, detail=f"Discord error: {e}")
    return member


# ── Moderation ────────────────────────────────────────────────────────────────

def _handle_discord_errors(fn):
    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        try:
            return await fn(*args, **kwargs)
        except discord.Forbidden:
            raise HTTPException(status_code=403, detail="Permission refusée — le bot n'a pas les droits nécessaires")
        except discord.NotFound:
            raise HTTPException(status_code=404, detail="Membre introuvable")
        except discord.HTTPException as e:
            raise HTTPException(status_code=502, detail=f"Erreur Discord: {e.text}")
    return wrapper


@app.post("/moderation/kick", dependencies=[Depends(_require_token)])
@_handle_discord_errors
async def kick_user(req: ModerationRequest):
    from utils.embed_style import send_sanction_dm
    guild  = _get_guild()
    member = await _get_member(guild, req.user_id)
    mod = guild.get_member(req.moderator_id)
    mod_name = mod.display_name if mod else None
    await send_sanction_dm(
        member, 'kick', req.reason,
        guild_name=guild.name,
        guild_icon_url=guild.icon.url if guild.icon else None,
        moderator_name=mod_name,
    )
    await member.kick(reason=req.reason)
    return {"success": True}

@app.post("/moderation/ban", dependencies=[Depends(_require_token)])
@_handle_discord_errors
async def ban_user(req: ModerationRequest):
    from utils.embed_style import send_sanction_dm
    guild  = _get_guild()
    member = await _get_member(guild, req.user_id)
    mod = guild.get_member(req.moderator_id)
    mod_name = mod.display_name if mod else None
    await send_sanction_dm(
        member, 'ban', req.reason,
        guild_name=guild.name,
        guild_icon_url=guild.icon.url if guild.icon else None,
        moderator_name=mod_name,
    )
    await member.ban(reason=req.reason)
    return {"success": True}

@app.post("/moderation/unban", dependencies=[Depends(_require_token)])
@_handle_discord_errors
async def unban_user(user_id: int):
    guild = _get_guild()
    user  = await _get_bot().fetch_user(user_id)
    await guild.unban(user)
    return {"success": True}

@app.post("/moderation/timeout", dependencies=[Depends(_require_token)])
@_handle_discord_errors
async def timeout_user(req: TempModerationRequest):
    from utils.embed_style import send_sanction_dm
    guild  = _get_guild()
    member = await _get_member(guild, req.user_id)
    mod = guild.get_member(req.moderator_id)
    mod_name = mod.display_name if mod else None
    await send_sanction_dm(
        member, 'timeout', req.reason,
        guild_name=guild.name,
        guild_icon_url=guild.icon.url if guild.icon else None,
        moderator_name=mod_name,
        duration=f"{req.duration_minutes} min",
    )
    until = datetime.now(timezone.utc) + timedelta(minutes=req.duration_minutes)
    await member.timeout(until, reason=req.reason)
    return {"success": True}

@app.post("/moderation/untimeout", dependencies=[Depends(_require_token)])
@_handle_discord_errors
async def untimeout_user(user_id: int):
    guild  = _get_guild()
    member = await _get_member(guild, user_id)
    await member.timeout(None)
    return {"success": True}


# ── Commands ──────────────────────────────────────────────────────────────────

@app.get("/commands", dependencies=[Depends(_require_token)])
async def list_commands():
    from utils.command_manager import CommandStatusManager
    statuses = await CommandStatusManager.get_all()
    bot = _get_bot()
    descriptions = {}
    for cmd in bot.tree.get_commands():
        if cmd.name not in statuses:
            statuses[cmd.name] = True
        descriptions[cmd.name] = cmd.description or ''
    return {"commands": statuses, "descriptions": descriptions}

@app.post("/commands/toggle", dependencies=[Depends(_require_token)])
async def toggle_command(req: CommandToggleRequest):
    from utils.command_manager import CommandStatusManager

    actor_name = None
    if req.moderator_id:
        try:
            guild = _get_guild()
            mod = guild.get_member(req.moderator_id)
            actor_name = mod.display_name if mod else str(req.moderator_id)
        except Exception:
            pass

    ok = await CommandStatusManager.set(req.command_name, req.enabled, req.guild_id,
                                         actor_name=actor_name)

    if ok and req.moderator_id and _bot:
        channel_id = int(os.getenv('ADMIN_LOG_CHANNEL_ID', '0') or '0')
        if channel_id:
            try:
                channel = _bot.get_channel(channel_id)
                if channel:
                    from utils.embed_style import hermes_embed, Colors
                    guild = _get_guild()
                    mod = guild.get_member(req.moderator_id)
                    mod_display = mod.mention if mod else f"<@{req.moderator_id}>"
                    status = "activée ✅" if req.enabled else "désactivée ❌"
                    embed = hermes_embed(
                        title="⚙️ Commande modifiée",
                        description=(
                            f"La commande **`/{req.command_name}`** a été **{status}**\n"
                            f"Par {mod_display} depuis le panel web."
                        ),
                        color=Colors.GREEN if req.enabled else Colors.ORANGE,
                    )
                    asyncio.create_task(channel.send(embed=embed))
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Command toggle notify failed: {e}")

    return {"success": ok}


# ── Tickets ──────────────────────────────────────────────────────────────────

class TicketCreateRequest(BaseModel):
    user_id: int
    username: str
    ticket_id: int
    title: str


class TicketMessageRequest(BaseModel):
    content: str
    author_name: str


@app.post("/tickets/create")
async def create_ticket_channel_endpoint(
    req: TicketCreateRequest, _=Depends(_require_token)
):
    bot = _get_bot()
    guild = _get_guild()
    cog = bot.cogs.get("TicketManagerCog")
    if not cog:
        raise HTTPException(status_code=500, detail="TicketManagerCog non chargé")
    member = await _get_member(guild, req.user_id)
    channel_id = await cog.create_ticket_channel(guild, member, req.ticket_id, req.title)
    cog._ticket_channels[channel_id] = req.ticket_id
    return {"discord_channel_id": channel_id}


@app.post("/tickets/{ticket_id}/message")
async def post_ticket_message_endpoint(
    ticket_id: int, req: TicketMessageRequest, _=Depends(_require_token)
):
    bot = _get_bot()
    cog = bot.cogs.get("TicketManagerCog")
    channel_id = next(
        (k for k, v in cog._ticket_channels.items() if v == ticket_id), None
    )
    if not channel_id:
        raise HTTPException(status_code=404, detail="Salon Discord introuvable")
    channel = bot.get_channel(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Salon Discord introuvable")
    await channel.send(f"**{req.author_name}** *(web)* : {req.content}")
    return {"success": True}


@app.post("/tickets/{ticket_id}/close")
async def close_ticket_channel_endpoint(ticket_id: int, _=Depends(_require_token)):
    bot = _get_bot()
    guild = _get_guild()
    cog = bot.cogs.get("TicketManagerCog")
    channel_id = next(
        (k for k, v in cog._ticket_channels.items() if v == ticket_id), None
    )
    if channel_id:
        channel = bot.get_channel(channel_id)
        if channel:
            embed = discord.Embed(
                title="🔒 Ticket fermé",
                description="Ce ticket a été fermé définitivement par un administrateur.",
                color=0xED4245,
            )
            embed.set_footer(text="Hermes · SaucisseLand")
            await channel.send(embed=embed)
            for target, overwrite in list(channel.overwrites.items()):
                if target != guild.me:
                    overwrite.send_messages = False
                    await channel.set_permissions(target, overwrite=overwrite)
        del cog._ticket_channels[channel_id]
    return {"success": True}


# ── Runner ────────────────────────────────────────────────────────────────────

def run_api():
    uvicorn.run(app, host="0.0.0.0", port=BOT_API_PORT, log_level="warning")
