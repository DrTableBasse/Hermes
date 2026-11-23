"""Internal Bot API — only reachable from the Docker network (web-api calls it)."""
import asyncio
import functools
import hmac
import logging
import os
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Annotated, Literal, Optional

import discord
import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Security
from fastapi.responses import Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel, Field, model_validator

from config import BOT_API_PORT, BOT_API_TOKEN

app  = FastAPI(title="Hermes Bot Internal API", docs_url=None, redoc_url=None)
_bot: Optional[discord.Client] = None
_security = HTTPBearer()


def set_bot_instance(bot: discord.Client):
    global _bot
    _bot = bot


def _require_token(creds: HTTPAuthorizationCredentials = Security(_security)):
    # Comparaison à temps constant ; un jeton vide n'est jamais accepté.
    if not BOT_API_TOKEN or not hmac.compare_digest(creds.credentials.encode(), BOT_API_TOKEN.encode()):
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
        from utils import settings
        if settings.get('admin_log_channel'):
            try:
                guild = _get_guild()
                channel = await settings.configured_channel(guild, 'admin_log_channel')
                if channel:
                    from utils.embed_style import hermes_embed, Colors
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


# ── Discord & réglages ────────────────────────────────────────────────────────

class EnsureChannelRequest(BaseModel):
    key: str


def _channel_kind(channel) -> str:
    if isinstance(channel, discord.CategoryChannel):
        return "category"
    if isinstance(channel, discord.ForumChannel):
        return "forum"
    if isinstance(channel, discord.VoiceChannel):
        return "voice"
    return "text"


@app.get("/discord/channels", dependencies=[Depends(_require_token)])
async def discord_channels():
    guild = _get_guild()
    return {"channels": [
        {"id": str(c.id), "name": c.name, "type": _channel_kind(c),
         "category": c.category.name if getattr(c, "category", None) else None}
        for c in sorted(guild.channels, key=lambda c: (c.position, c.id))
    ]}


def _bot_top_position(guild: discord.Guild) -> int:
    return guild.me.top_role.position


def _role_payload(guild: discord.Guild, r: discord.Role) -> dict:
    return {
        "id": str(r.id), "name": r.name, "color": r.color.value,
        "position": r.position, "managed": r.managed,
        "members": len(r.members), "below_bot": r.position < _bot_top_position(guild),
    }


@app.get("/discord/roles", dependencies=[Depends(_require_token)])
async def discord_roles():
    guild = _get_guild()
    return {"roles": [
        _role_payload(guild, r)
        for r in sorted(guild.roles, key=lambda r: -r.position) if not r.is_default()
    ]}


# ── Rôles : gestion depuis le site ───────────────────────────────────────────

DiscordId = Annotated[str, Field(pattern=r"^\d{1,20}$")]
BULK_MAX = 500  # jamais plus de membres par lot


def _site_reason(actor_name: str) -> str:
    """Raison d'audit Discord : rattache l'entrée Discord à la ligne du journal du site."""
    return f"via le site par {actor_name}"


def _managed_role(guild: discord.Guild, role_id: int) -> discord.Role:
    """Rôle que le bot peut gérer : ni @everyone, ni managed, strictement sous le bot."""
    role = guild.get_role(role_id)
    if role is None:
        raise HTTPException(status_code=404, detail="Rôle introuvable")
    if role.is_default():
        raise HTTPException(status_code=403, detail="Le rôle @everyone ne peut pas être géré depuis le site")
    if role.managed:
        raise HTTPException(status_code=403,
                            detail="Ce rôle est géré par une intégration et ne peut pas être modifié")
    if role.position >= _bot_top_position(guild):
        raise HTTPException(status_code=403, detail="Ce rôle n'est pas sous le rôle le plus haut du bot")
    return role


class ActorRequest(BaseModel):
    actor_name: str = Field(min_length=1, max_length=100)


class RoleCreateRequest(ActorRequest):
    name:        str = Field(min_length=1, max_length=100)
    color:       int = Field(default=0, ge=0, le=0xFFFFFF)
    hoist:       bool = False
    mentionable: bool = False


class RoleUpdateRequest(ActorRequest):
    name:        Optional[str] = Field(default=None, min_length=1, max_length=100)
    color:       Optional[int] = Field(default=None, ge=0, le=0xFFFFFF)
    hoist:       Optional[bool] = None
    mentionable: Optional[bool] = None
    position:    Optional[int] = Field(default=None, ge=1)


@app.post("/discord/roles", dependencies=[Depends(_require_token)])
@_handle_discord_errors
async def create_role(req: RoleCreateRequest):
    guild = _get_guild()
    # Discord crée le rôle en bas de la liste, donc sous le rôle du bot.
    role = await guild.create_role(
        name=req.name, colour=discord.Colour(req.color), hoist=req.hoist,
        mentionable=req.mentionable, reason=_site_reason(req.actor_name),
    )
    return _role_payload(guild, role)


@app.patch("/discord/roles/{role_id}", dependencies=[Depends(_require_token)])
@_handle_discord_errors
async def update_role(role_id: int, req: RoleUpdateRequest):
    guild = _get_guild()
    role = _managed_role(guild, role_id)
    changes: dict = {}
    if req.name is not None:
        changes["name"] = req.name
    if req.color is not None:
        changes["colour"] = discord.Colour(req.color)
    if req.hoist is not None:
        changes["hoist"] = req.hoist
    if req.mentionable is not None:
        changes["mentionable"] = req.mentionable
    if req.position is not None:  # bornée strictement sous le rôle du bot
        changes["position"] = max(1, min(req.position, _bot_top_position(guild) - 1))
    if changes:
        role = await role.edit(**changes, reason=_site_reason(req.actor_name)) or role
    return _role_payload(guild, role)


@app.delete("/discord/roles/{role_id}", dependencies=[Depends(_require_token)])
@_handle_discord_errors
async def delete_role(role_id: int, req: ActorRequest):
    guild = _get_guild()
    role = _managed_role(guild, role_id)
    await role.delete(reason=_site_reason(req.actor_name))
    return {"ok": True}


@app.post("/discord/members/{user_id}/roles/{role_id}", dependencies=[Depends(_require_token)])
@_handle_discord_errors
async def add_member_role(user_id: int, role_id: int, req: ActorRequest):
    guild = _get_guild()
    role = _managed_role(guild, role_id)
    member = await _get_member(guild, user_id)
    await member.add_roles(role, reason=_site_reason(req.actor_name))
    return {"ok": True}


@app.delete("/discord/members/{user_id}/roles/{role_id}", dependencies=[Depends(_require_token)])
@_handle_discord_errors
async def remove_member_role(user_id: int, role_id: int, req: ActorRequest):
    guild = _get_guild()
    role = _managed_role(guild, role_id)
    member = await _get_member(guild, user_id)
    await member.remove_roles(role, reason=_site_reason(req.actor_name))
    return {"ok": True}


# ── Travaux en arrière-plan (lots, application de règle) ─────────────────────
# En mémoire seulement : au redémarrage du bot, un travail inconnu répond 404
# (le site l'affiche « interrompu ») ; rien n'est repris silencieusement.

JOB_TTL_S = 3600   # un travail terminé est oublié au bout d'une heure
JOBS_MAX = 200     # borne du dictionnaire
_jobs: dict[str, dict] = {}
_job_tasks: set[asyncio.Task] = set()  # références fortes : la tâche n'est pas ramassée


def _purge_jobs() -> None:
    now = time.monotonic()
    for job_id, job in list(_jobs.items()):
        if job["finished_at"] is not None and now - job["finished_at"] > JOB_TTL_S:
            del _jobs[job_id]
    if len(_jobs) >= JOBS_MAX:  # encore plein : les plus anciens travaux terminés partent
        finished = sorted((j["finished_at"], k) for k, j in _jobs.items() if j["finished_at"] is not None)
        for _, job_id in finished[:len(_jobs) - JOBS_MAX + 1]:
            del _jobs[job_id]
    if len(_jobs) >= JOBS_MAX:
        raise HTTPException(status_code=429, detail="Trop de travaux en cours, réessayez plus tard")


def _start_job(total: int, run, **extra) -> str:
    """Crée l'état du travail et lance ``run(job)`` en tâche asyncio ; renvoie son identifiant."""
    _purge_jobs()
    job_id = uuid.uuid4().hex
    job = {"state": "running", "done": 0, "total": total, "errors": 0, **extra, "finished_at": None}
    _jobs[job_id] = job

    async def runner():
        try:
            await run(job)
            job["state"] = "done"
        except asyncio.CancelledError:
            job["state"] = "interrupted"  # arrêt du bot en cours de travail
            raise
        except Exception as e:
            logging.getLogger(__name__).error("Travail %s en échec : %s", job_id, e, exc_info=True)
            job["state"] = "failed"
        finally:
            job["finished_at"] = time.monotonic()

    task = asyncio.create_task(runner())
    _job_tasks.add(task)
    task.add_done_callback(_job_tasks.discard)
    return job_id


class BulkRequest(ActorRequest):
    action:       Literal["add", "remove"]
    user_ids:     Optional[list[DiscordId]] = Field(default=None, max_length=BULK_MAX)
    from_role_id: Optional[DiscordId] = None

    @model_validator(mode="after")
    def _one_source(self):
        if (self.user_ids is None) == (self.from_role_id is None):
            raise ValueError("indiquer soit user_ids, soit from_role_id")
        return self


@app.post("/discord/roles/{role_id}/bulk", dependencies=[Depends(_require_token)])
async def bulk_role(role_id: int, req: BulkRequest):
    """Ajoute ou retire un rôle à une liste de membres (ou aux porteurs d'un autre rôle)."""
    guild = _get_guild()
    role = _managed_role(guild, role_id)
    if req.user_ids is not None:
        user_ids = list(dict.fromkeys(int(u) for u in req.user_ids))
    else:
        source = guild.get_role(int(req.from_role_id))
        if source is None:
            raise HTTPException(status_code=404, detail="Rôle source introuvable")
        user_ids = [m.id for m in source.members if not m.bot]
        if len(user_ids) > BULK_MAX:
            raise HTTPException(status_code=422,
                                detail=f"Le rôle source compte plus de {BULK_MAX} membres : lot refusé")
    add = req.action == "add"
    reason = _site_reason(req.actor_name)

    async def run(job):
        for user_id in user_ids:  # séquentiel : discord.py gère les limites
            member = guild.get_member(user_id)
            try:
                if member is None:
                    job["errors"] += 1
                elif add and role not in member.roles:
                    await member.add_roles(role, reason=reason)
                elif not add and role in member.roles:
                    await member.remove_roles(role, reason=reason)
            except discord.HTTPException:
                job["errors"] += 1
            job["done"] += 1

    return {"job_id": _start_job(len(user_ids), run)}


@app.get("/discord/jobs/{job_id}", dependencies=[Depends(_require_token)])
async def get_job(job_id: str):
    job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Travail inconnu (bot redémarré ou travail expiré)")
    return {k: v for k, v in job.items() if k != "finished_at"}


# ── Règles de rôles ───────────────────────────────────────────────────────────

def _role_engine():
    cog = _get_bot().get_cog("RoleEngine")
    if cog is None:
        raise HTTPException(status_code=503, detail="Moteur de règles non chargé")
    return cog


def _members_brief(guild: discord.Guild, user_ids: list[int]) -> list[dict]:
    out = []
    for uid in user_ids:
        m = guild.get_member(uid)
        out.append({"id": str(uid), "name": m.display_name if m else None})
    return out


@app.post("/role-rules/reload", dependencies=[Depends(_require_token)])
async def role_rules_reload():
    await _role_engine().reload()
    return {"ok": True}


@app.get("/role-rules/{rule_id}/preview", dependencies=[Depends(_require_token)])
async def role_rule_preview(rule_id: int):
    engine = _role_engine()
    guild = _get_guild()
    try:
        result = await engine.preview(rule_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Règle introuvable")
    return {
        "gain": _members_brief(guild, result["gain"]),
        "lose": _members_brief(guild, result["lose"]),
        "missing_role": result["missing_role"],
    }


@app.post("/role-rules/{rule_id}/apply", dependencies=[Depends(_require_token)])
async def role_rule_apply(rule_id: int):
    """Applique une règle à tous les membres en arrière-plan ; renvoie un identifiant de travail.

    Le moteur ne publie pas sa progression : ``total``/``done`` sont connus à la fin
    (gagnants + perdants), ``added``/``removed`` comptent les changements réels et
    ``skipped`` les membres déjà pourvus (rôle homonyme réutilisé), ``errors`` les
    seuls échecs : ``total − added − removed − skipped``.
    """
    engine = _role_engine()
    try:
        await engine._find_rule(rule_id)  # 404 immédiat plutôt qu'un travail en échec
    except KeyError:
        raise HTTPException(status_code=404, detail="Règle introuvable")

    async def run(job):
        result = await engine.apply(rule_id)
        changed = result["added"] + result["removed"]
        job["total"] = job["done"] = len(result["gain"]) + len(result["lose"])
        job["errors"] = job["total"] - changed - result["skipped"]
        job["added"], job["removed"] = result["added"], result["removed"]
        job["skipped"] = result["skipped"]
        job["missing_role"] = result["missing_role"]

    return {"job_id": _start_job(0, run, added=0, removed=0, skipped=0, missing_role=False)}


@app.get("/discord/members/{user_id}/rank", dependencies=[Depends(_require_token)])
async def discord_member_rank(user_id: int):
    """Rang Discord d'un membre (anti-escalade des accès au site) ; 404 si absent du serveur."""
    guild = _get_guild()
    member = await _get_member(guild, user_id)
    return {
        "top_position": member.top_role.position,
        "is_owner": guild.owner_id == member.id,
        "role_ids": [str(r.id) for r in member.roles if not r.is_default()],
    }


@app.post("/settings/reload", dependencies=[Depends(_require_token)])
async def settings_reload():
    from utils import settings
    await settings.load()
    return {"ok": True}


@app.post("/settings/ensure-channel", dependencies=[Depends(_require_token)])
@_handle_discord_errors
async def settings_ensure_channel(req: EnsureChannelRequest):
    from utils import settings
    guild = _get_guild()
    try:
        channel = await settings.ensure_channel(guild, req.key)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"id": str(channel.id), "name": channel.name}


# ── Statut d'Hermes ───────────────────────────────────────────────────────────

@app.get("/status", dependencies=[Depends(_require_token)])
async def status():
    from utils.runtime import STARTED_AT
    bot = _get_bot()
    latency = bot.latency  # secondes ; nan/inf tant que la passerelle n'a pas répondu
    latency_ms = int(round(latency * 1000)) if latency == latency and latency != float("inf") else 0
    return {
        "ready": bot.is_ready(),
        "latency_ms": latency_ms,
        "started_at": STARTED_AT.isoformat(),
        "guilds": len(bot.guilds),
    }


# ── Caserne en direct ─────────────────────────────────────────────────────────

@app.get("/live", dependencies=[Depends(_require_token)])
async def live():
    cog = _get_bot().get_cog('LiveStats')
    if cog is None:
        raise HTTPException(status_code=503, detail="LiveStats not loaded")
    return cog.collect(_get_guild())


# ── Events programmés ─────────────────────────────────────────────────────────

def _event_payload(guild: discord.Guild, ev: discord.ScheduledEvent) -> dict:
    return {
        "id": str(ev.id), "name": ev.name, "description": ev.description,
        "start": ev.start_time.isoformat(),
        "end": ev.end_time.isoformat() if ev.end_time else None,
        "status": ev.status.name,
        "location": ev.location or (ev.channel.name if ev.channel else None),
        "user_count": ev.user_count,
        "creator_id": str(ev.creator_id) if ev.creator_id else None,
        "image": ev.cover_image.url if ev.cover_image else None,
        "url": f"https://discord.com/events/{guild.id}/{ev.id}",
    }


@app.get("/events", dependencies=[Depends(_require_token)])
async def events():
    guild = _get_guild()
    upcoming = (discord.EventStatus.scheduled, discord.EventStatus.active)
    return {"events": [
        _event_payload(guild, ev)
        for ev in sorted(guild.scheduled_events, key=lambda e: e.start_time)
        if ev.status in upcoming
    ]}


# ── État-major ────────────────────────────────────────────────────────────────

def collect_staff(guild: discord.Guild) -> list[dict]:
    """Membres portant ``admin_role`` ou ``mod_role`` (administration prioritaire).

    Le libellé ``role`` est le nom du rôle Discord réel ; un rôle non réglé est ignoré.
    """
    from utils import settings
    staff: dict[int, dict] = {}
    for key in ("admin_role", "mod_role"):  # l'ordre fixe la priorité
        role = settings.get_role(guild, key)
        if role is None:
            continue
        for member in role.members:
            if member.bot or member.id in staff:
                continue
            staff[member.id] = {
                "id": str(member.id), "name": member.display_name,
                "avatar": member.display_avatar.url, "role": role.name,
            }
    return list(staff.values())


@app.get("/staff", dependencies=[Depends(_require_token)])
async def staff():
    return collect_staff(_get_guild())


# ── Runner ────────────────────────────────────────────────────────────────────

def run_api():
    uvicorn.run(app, host="0.0.0.0", port=BOT_API_PORT, log_level="warning")
