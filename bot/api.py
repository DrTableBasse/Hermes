"""Internal Bot API — only reachable from the Docker network (web-api calls it)."""
import asyncio
import os
from datetime import datetime, timezone, timedelta
from typing import Optional

import discord
import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
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


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    ready = _bot is not None and _bot.is_ready()
    return {"status": "ok" if ready else "starting", "ready": ready}


# ── Warns ─────────────────────────────────────────────────────────────────────

@app.post("/warns", dependencies=[Depends(_require_token)])
async def add_warn(req: WarnRequest):
    from utils.database import warn_manager
    ok = await warn_manager.add_warn(req.user_id, req.reason, req.moderator_id)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to add warn")
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


# ── Moderation ────────────────────────────────────────────────────────────────

@app.post("/moderation/kick", dependencies=[Depends(_require_token)])
async def kick_user(req: ModerationRequest):
    guild  = _get_guild()
    member = guild.get_member(req.user_id)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    await member.kick(reason=req.reason)
    return {"success": True}

@app.post("/moderation/ban", dependencies=[Depends(_require_token)])
async def ban_user(req: ModerationRequest):
    guild  = _get_guild()
    member = guild.get_member(req.user_id)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    await member.ban(reason=req.reason)
    return {"success": True}

@app.post("/moderation/unban", dependencies=[Depends(_require_token)])
async def unban_user(user_id: int):
    guild = _get_guild()
    user  = await _get_bot().fetch_user(user_id)
    await guild.unban(user)
    return {"success": True}

@app.post("/moderation/timeout", dependencies=[Depends(_require_token)])
async def timeout_user(req: TempModerationRequest):
    guild  = _get_guild()
    member = guild.get_member(req.user_id)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    until = datetime.now(timezone.utc) + timedelta(minutes=req.duration_minutes)
    await member.timeout(until, reason=req.reason)
    return {"success": True}

@app.post("/moderation/untimeout", dependencies=[Depends(_require_token)])
async def untimeout_user(user_id: int):
    guild  = _get_guild()
    member = guild.get_member(user_id)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    await member.timeout(None)
    return {"success": True}


# ── Commands ──────────────────────────────────────────────────────────────────

@app.get("/commands", dependencies=[Depends(_require_token)])
async def list_commands():
    from utils.command_manager import CommandStatusManager
    statuses = await CommandStatusManager.get_all()
    return {"commands": statuses}

@app.post("/commands/toggle", dependencies=[Depends(_require_token)])
async def toggle_command(req: CommandToggleRequest):
    from utils.command_manager import CommandStatusManager
    ok = await CommandStatusManager.set(req.command_name, req.enabled, req.guild_id)
    return {"success": ok}


# ── Runner ────────────────────────────────────────────────────────────────────

def run_api():
    uvicorn.run(app, host="0.0.0.0", port=BOT_API_PORT, log_level="warning")
