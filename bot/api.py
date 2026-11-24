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
from fastapi import Path as FastApiPath
from fastapi.responses import Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel, Field, model_validator

from cogs.fun.game_manager import GameRefused
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
    # Commandes globales et commandes de serveur (commandes de jeux, cogs/fun/game_manager.py).
    guild = discord.Object(id=int(os.getenv('GUILD_ID', '0')))
    for cmd in [*bot.tree.get_commands(), *bot.tree.get_commands(guild=guild)]:
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


# ── Salons et modèles d'accès (étape 5) ──────────────────────────────────────
# Le droit « channels.manage » et le réservé admin du modèle « staff » sont vérifiés
# par web-api ; ici : visibilité du salon pour l'acteur (permissions effectives Discord,
# propriétaire exempté), rôles R strictement sous l'acteur, pas de retrait de surcharge
# d'un rôle au-dessus de lui, jeton d'aperçu (409 si l'état a changé).

from utils import channels_api  # noqa: E402
from utils.channel_templates import TEMPLATES  # noqa: E402

ChannelType = Literal["text", "voice", "forum", "announcement", "category"]
TemplateName = Literal["public", "role_required", "announcements", "staff"]
_templates_lock = asyncio.Lock()  # aperçu vérifié et application : pas d'entrelacement
STALE_PREVIEW = "L'aperçu n'est plus à jour : relancez l'aperçu avant d'appliquer"


def _channel_errors(fn):
    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        try:
            return await fn(*args, **kwargs)
        except discord.Forbidden:
            raise HTTPException(status_code=403, detail="Permission refusée — le bot n'a pas les droits "
                                                        "nécessaires (Gérer les salons, Gérer les rôles)")
        except discord.NotFound:
            raise HTTPException(status_code=404, detail="Salon introuvable sur Discord")
        except discord.HTTPException as e:
            if e.status == 400:  # nom refusé, position impossible…
                raise HTTPException(status_code=422, detail=f"Refusé par Discord : {e.text or e.status}")
            raise HTTPException(status_code=502, detail=f"Erreur Discord : {e.text or e.status}")
    return wrapper


async def _actor(guild: discord.Guild, actor_id: int) -> discord.Member:
    """Acteur du site ; absent du serveur Discord → 403."""
    member = guild.get_member(actor_id)
    if member is None:
        try:
            member = await guild.fetch_member(actor_id)
        except discord.NotFound:
            raise HTTPException(status_code=403, detail="Vous n'êtes pas membre du serveur Discord")
    return member


def _get_channel(guild: discord.Guild, channel_id: int):
    channel = guild.get_channel(channel_id)
    if channel is None or channels_api.channel_type(channel) is None:
        raise HTTPException(status_code=404, detail="Salon introuvable")
    return channel


def _require_view(guild: discord.Guild, actor: discord.Member, channels: list) -> None:
    for channel in channels:
        if not channels_api.can_view(guild, actor, channel):
            raise HTTPException(status_code=403,
                                detail="Vous ne voyez pas l'un des salons concernés dans Discord.")


def _is_owner(guild: discord.Guild, actor: discord.Member) -> bool:
    return guild.owner_id == actor.id


def _template_roles(guild: discord.Guild, actor: discord.Member, template: str,
                    role_ids: list[str]) -> list[int]:
    """Rôles R validés : existants, pas @everyone, strictement sous l'acteur (sauf propriétaire)."""
    if template not in ("role_required", "announcements"):
        return []
    if not role_ids:
        raise HTTPException(status_code=422, detail="Choisissez au moins un rôle pour ce modèle")
    roles = []
    for rid in dict.fromkeys(int(r) for r in role_ids):
        role = guild.get_role(rid)
        if role is None:
            raise HTTPException(status_code=404, detail="Rôle introuvable")
        if role.is_default():
            raise HTTPException(status_code=422, detail="@everyone ne peut pas être un rôle requis")
        if not _is_owner(guild, actor) and role.position >= actor.top_role.position:
            raise HTTPException(status_code=403,
                                detail=f"Le rôle « {role.name} » n'est pas sous votre rôle le plus haut")
        roles.append(rid)
    return roles


def _staff_role_ids(guild: discord.Guild) -> list[int]:
    from utils import settings
    return [r.id for r in settings.get_roles(guild, "staff_roles")]


def _check_role_changes(guild: discord.Guild, actor: discord.Member, changes: list[dict]) -> None:
    """On ne modifie pas (ajout, modification, retrait) la surcharge d'un rôle au même niveau
    ou au-dessus de son rôle le plus haut (sauf propriétaire)."""
    if _is_owner(guild, actor):
        return
    for c in changes:
        if c["target_type"] != "role":
            continue
        role = guild.get_role(c["target_id"])
        if role is not None and not role.is_default() and role.position >= actor.top_role.position:
            raise HTTPException(status_code=403, detail=f"Impossible de modifier la surcharge du rôle "
                                                        f"« {role.name} », au-dessus de votre rôle le plus haut")


async def _build_template_plan(guild, actor, channel, template, role_ids, sync_children):
    """Plan d'un modèle : ``(entrées par salon, jeton, rôles enregistrés)`` ; contrôles d'accès inclus."""
    targets = channels_api.targets_of(channel, sync_children)
    _require_view(guild, actor, targets)
    roles = _template_roles(guild, actor, template, role_ids)
    staff = _staff_role_ids(guild)
    if template == "staff" and not staff:
        raise HTTPException(status_code=422, detail="Aucun rôle staff n'est réglé (staff_roles)")
    saved = roles if template != "staff" else staff
    memo = await channels_api.load_templates()
    entries = []
    for ch in targets:
        previous = list((memo.get(ch.id) or {}).get("roles") or [])
        try:
            current, changes = channels_api.channel_plan(guild, ch, template, roles, staff, previous)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        _check_role_changes(guild, actor, changes)
        entries.append((ch, current, changes))
    token = channels_api.combined_token(
        [(ch.id, cur) for ch, cur, _ in entries],
        [template, sorted(roles), sorted(staff), bool(sync_children)])
    return entries, token, saved


def _preview_payload(guild, entries, token) -> dict:
    return {
        "channels": [{"id": str(ch.id), "name": ch.name, "type": channels_api.channel_type(ch),
                      "changes": channels_api.describe_changes(guild, changes)}
                     for ch, _, changes in entries],
        "count": len(entries),
        "token": token,
    }


async def _apply_entries(guild, entries, template, saved_roles, actor_id, actor_name) -> dict:
    """Écrit chaque salon séquentiellement ; continue après un échec, relance si tout échoue."""
    reason = _site_reason(actor_name)
    applied, failed, memo_failed, last_error = 0, [], [], None
    for ch, _, changes in entries:
        try:
            if changes:
                await ch.edit(overwrites=channels_api.new_overwrites(guild, ch, changes), reason=reason)
        except discord.HTTPException as e:
            last_error = e
            failed.append({"id": str(ch.id), "name": ch.name, "error": e.text or str(e.status)})
            continue
        applied += 1  # Discord fait foi : le salon est écrit
        try:
            await channels_api.save_template(ch.id, template, saved_roles, actor_id)
        except Exception:
            logging.getLogger(__name__).exception("Mémorisation du modèle impossible (salon %s « %s », modèle %s, acteur %s)",
                             ch.id, ch.name, template, actor_id)
            memo_failed.append(str(ch.id))
    if entries and applied == 0 and last_error is not None:
        raise last_error
    return {"applied": applied, "failed": failed, "memo_failed": memo_failed}


class ChannelCreateRequest(ActorRequest):
    actor_id:  DiscordId
    name:      str = Field(min_length=1, max_length=100)
    type:      ChannelType
    parent_id: Optional[DiscordId] = None


class ChannelUpdateRequest(ActorRequest):
    actor_id:  DiscordId
    name:      Optional[str] = Field(default=None, min_length=1, max_length=100)
    parent_id: Optional[DiscordId] = None  # présent à null : sortir de la catégorie
    position:  Optional[int] = Field(default=None, ge=0)


class ChannelDeleteRequest(ActorRequest):
    actor_id: DiscordId


class TemplatePreviewRequest(BaseModel):
    template:      TemplateName
    roles:         list[DiscordId] = Field(default_factory=list, max_length=25)
    sync_children: bool = False
    actor_id:      DiscordId


class TemplateApplyRequest(TemplatePreviewRequest, ActorRequest):
    token: str = Field(min_length=1, max_length=64)


class StaffResyncPreviewRequest(BaseModel):
    actor_id: DiscordId


class StaffResyncApplyRequest(StaffResyncPreviewRequest, ActorRequest):
    token: str = Field(min_length=1, max_length=64)


def _tree_item(guild, actor, ch, memo: dict) -> dict:
    row = memo.get(ch.id)
    return {
        "id": str(ch.id), "name": ch.name, "type": channels_api.channel_type(ch),
        "position": ch.position,
        "parent_id": str(ch.category_id) if getattr(ch, "category_id", None) else None,
        "overwrites": len(ch.overwrites),
        "template": None if row is None else {
            "template": row["template"], "roles": [str(r) for r in (row["roles"] or [])],
            "applied_by": str(row["applied_by"]) if row["applied_by"] else None,
            "applied_at": row["applied_at"].isoformat() if row["applied_at"] else None,
        },
        "visible_to_actor": channels_api.can_view(guild, actor, ch),
    }


@app.get("/discord/channels/tree", dependencies=[Depends(_require_token)])
async def channels_tree(actor_id: int):
    """Catégories et salons dans l'ordre Discord (liste à plat, ``parent_id`` pour l'arbre)."""
    guild = _get_guild()
    actor = await _actor(guild, actor_id)
    memo = await channels_api.load_templates()
    return {"channels": [_tree_item(guild, actor, ch, memo)
                         for ch in channels_api.ordered_channels(guild)
                         if channels_api.channel_type(ch) is not None],
            "templates": list(TEMPLATES)}


def _parent_category(guild: discord.Guild, parent_id: Optional[str]):
    if parent_id is None:
        return None
    parent = guild.get_channel(int(parent_id))
    if parent is None or channels_api.channel_type(parent) != "category":
        raise HTTPException(status_code=404, detail="Catégorie introuvable")
    return parent


@app.post("/discord/channels", dependencies=[Depends(_require_token)])
@_channel_errors
async def create_channel(req: ChannelCreateRequest):
    guild = _get_guild()
    actor = await _actor(guild, int(req.actor_id))
    reason = _site_reason(req.actor_name)
    if req.type == "category":
        if req.parent_id is not None:
            raise HTTPException(status_code=422, detail="Une catégorie ne peut pas être dans une catégorie")
        channel = await guild.create_category(req.name, reason=reason)
    else:
        parent = _parent_category(guild, req.parent_id)
        if parent is not None:
            _require_view(guild, actor, [parent])
        if req.type == "voice":
            channel = await guild.create_voice_channel(req.name, category=parent, reason=reason)
        elif req.type == "forum":
            channel = await guild.create_forum(req.name, category=parent, reason=reason)
        else:
            channel = await guild.create_text_channel(req.name, category=parent, reason=reason,
                                                      news=req.type == "announcement")
    return {"id": str(channel.id), "name": channel.name, "type": req.type,
            "parent_id": req.parent_id}


@app.patch("/discord/channels/{channel_id}", dependencies=[Depends(_require_token)])
@_channel_errors
async def update_channel(channel_id: int, req: ChannelUpdateRequest):
    guild = _get_guild()
    channel = _get_channel(guild, channel_id)
    actor = await _actor(guild, int(req.actor_id))
    _require_view(guild, actor, [channel])
    changes: dict = {}
    if req.name is not None:
        changes["name"] = req.name
    if "parent_id" in req.model_fields_set:
        if channels_api.channel_type(channel) == "category":
            raise HTTPException(status_code=422, detail="Une catégorie ne peut pas être dans une catégorie")
        parent = _parent_category(guild, req.parent_id)
        if parent is not None:
            _require_view(guild, actor, [parent])
        changes["category"] = parent
    if req.position is not None:
        changes["position"] = req.position
    if changes:
        channel = await channel.edit(**changes, reason=_site_reason(req.actor_name)) or channel
    return {"id": str(channel.id), "name": channel.name, "position": channel.position,
            "parent_id": str(channel.category_id) if getattr(channel, "category_id", None) else None}


@app.delete("/discord/channels/{channel_id}", dependencies=[Depends(_require_token)])
@_channel_errors
async def delete_channel(channel_id: int, req: ChannelDeleteRequest):
    guild = _get_guild()
    channel = _get_channel(guild, channel_id)
    _require_view(guild, await _actor(guild, int(req.actor_id)), [channel])
    if channels_api.channel_type(channel) == "category" and channel.channels:
        raise HTTPException(status_code=409, detail="Videz d'abord la catégorie : elle contient "
                                                    f"{len(channel.channels)} salon(s)")
    await channel.delete(reason=_site_reason(req.actor_name))
    memo_failed = []
    try:
        await channels_api.delete_template(channel_id)
    except Exception:
        # Discord fait foi : le salon est supprimé ; le mémo orphelin est seulement signalé.
        logging.getLogger(__name__).exception(
            "Oubli du modèle impossible après suppression du salon %s (acteur %s)", channel_id, req.actor_id)
        memo_failed.append(str(channel_id))
    return {"ok": True, "memo_failed": memo_failed}


@app.post("/discord/channels/staff-resync/preview", dependencies=[Depends(_require_token)])
@_channel_errors
async def staff_resync_preview(req: StaffResyncPreviewRequest):
    """Salons mémorisés au modèle « staff » : passage aux rôles ``staff_roles`` actuels."""
    guild = _get_guild()
    entries, token = await _staff_resync_plan(guild, await _actor(guild, int(req.actor_id)))
    return _preview_payload(guild, entries, token)


@app.post("/discord/channels/staff-resync/apply", dependencies=[Depends(_require_token)])
@_channel_errors
async def staff_resync_apply(req: StaffResyncApplyRequest):
    guild = _get_guild()
    actor = await _actor(guild, int(req.actor_id))
    async with _templates_lock:
        entries, token = await _staff_resync_plan(guild, actor)
        if not hmac.compare_digest(token.encode(), req.token.encode()):
            raise HTTPException(status_code=409, detail=STALE_PREVIEW)
        return await _apply_entries(guild, entries, "staff", _staff_role_ids(guild),
                                    actor.id, req.actor_name)


async def _staff_resync_plan(guild, actor):
    staff = _staff_role_ids(guild)
    if not staff:
        raise HTTPException(status_code=422, detail="Aucun rôle staff n'est réglé (staff_roles)")
    memo = await channels_api.load_templates()
    targets = [ch for cid, row in sorted(memo.items()) if row["template"] == "staff"
               and (ch := guild.get_channel(cid)) is not None and channels_api.channel_type(ch)]
    _require_view(guild, actor, targets)
    entries = []
    for ch in targets:
        current, changes = channels_api.channel_plan(guild, ch, "staff", [], staff,
                                                     list(memo[ch.id]["roles"] or []))
        _check_role_changes(guild, actor, changes)
        entries.append((ch, current, changes))
    token = channels_api.combined_token([(ch.id, cur) for ch, cur, _ in entries],
                                        ["staff-resync", sorted(staff)])
    return entries, token


@app.post("/discord/channels/{channel_id}/template/preview", dependencies=[Depends(_require_token)])
@_channel_errors
async def template_preview(channel_id: int, req: TemplatePreviewRequest):
    guild = _get_guild()
    channel = _get_channel(guild, channel_id)
    actor = await _actor(guild, int(req.actor_id))
    entries, token, _ = await _build_template_plan(guild, actor, channel, req.template,
                                                   req.roles, req.sync_children)
    return _preview_payload(guild, entries, token)


@app.post("/discord/channels/{channel_id}/template/apply", dependencies=[Depends(_require_token)])
@_channel_errors
async def template_apply(channel_id: int, req: TemplateApplyRequest):
    """Applique le modèle prévisualisé ; 409 si l'état des salons a changé depuis l'aperçu."""
    guild = _get_guild()
    channel = _get_channel(guild, channel_id)
    actor = await _actor(guild, int(req.actor_id))
    async with _templates_lock:
        entries, token, saved = await _build_template_plan(guild, actor, channel, req.template,
                                                           req.roles, req.sync_children)
        if not hmac.compare_digest(token.encode(), req.token.encode()):
            raise HTTPException(status_code=409, detail=STALE_PREVIEW)
        return await _apply_entries(guild, entries, req.template, saved, actor.id, req.actor_name)


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


# ── Jeux (cogs/fun/game_manager.py) ──────────────────────────────────────────
# Le site écrit site_games puis appelle ces routes ; le cog GameManager fait foi pour
# Discord (rôle, forum, commande). Ses erreurs Discord sont relancées une fois l'état
# remis en cohérence : elles sont traduites ici en français.

GameKey = Annotated[str, FastApiPath(pattern=r"^[a-z0-9-]{1,32}$")]


def _game_manager():
    cog = _get_bot().get_cog("GameManager")
    if cog is None:
        raise HTTPException(status_code=503, detail="Gestion des jeux non chargée")
    return cog


def _game_errors(fn):
    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        try:
            return await fn(*args, **kwargs)
        except KeyError:
            raise HTTPException(status_code=404, detail="Jeu inconnu")
        except GameRefused as e:  # homonyme non rattachable, rôle à permissions, forum d'un autre jeu
            raise HTTPException(status_code=409, detail=str(e))
        except RuntimeError as e:  # serveur Discord introuvable
            raise HTTPException(status_code=503, detail=str(e) or "Serveur Discord introuvable")
        except discord.Forbidden:
            raise HTTPException(status_code=403, detail="Permission refusée — le bot n'a pas les droits "
                                                        "nécessaires (Gérer les rôles, Gérer les salons)")
        except discord.NotFound:
            raise HTTPException(status_code=404, detail="Rôle ou salon Discord introuvable")
        except discord.HTTPException as e:
            raise HTTPException(status_code=502, detail=f"Erreur Discord : {e.text or e.status}")
    return wrapper


def _resync_forum_count(cog, statuses: dict) -> int:
    """Forums que ``resync_permissions`` réécrirait : jeux provisionnés dont le forum existe."""
    return sum(1 for key, game in cog.games.items()
               if game.provisioned and statuses.get(key, {}).get("forum") == "ok")


@app.post("/games/reload", dependencies=[Depends(_require_token)])
async def games_reload():
    await _game_manager().reload()
    return {"ok": True}


@app.get("/games/status", dependencies=[Depends(_require_token)])
async def games_status():
    """État Discord de chaque jeu (``ok`` / ``missing`` / ``none``) et nombre de forums à resynchroniser."""
    cog = _game_manager()
    statuses = cog.statuses()
    return {"loaded": bool(cog.loaded), "games": statuses,
            "resync_forums": _resync_forum_count(cog, statuses)}


@app.get("/games/taken", dependencies=[Depends(_require_token)])
async def games_taken(exclude: Optional[str] = None):
    """Noms de commande et émojis déjà pris pour le jeu ``exclude`` (création : aucun)."""
    cog = _game_manager()
    return {"commands": sorted(cog.taken_command_names(exclude)),
            "emojis": sorted(cog.taken_emojis(exclude))}


@app.post("/games/resync-permissions", dependencies=[Depends(_require_token)])
@_game_errors
async def games_resync_permissions():
    """Réécrit les forums de jeux ; ``failed`` : forums restés en échec (les autres sont faits)."""
    return await _game_manager().resync_permissions()


@app.get("/games/resync-preview", dependencies=[Depends(_require_token)])
@_game_errors
async def games_resync_preview():
    """Lecture seule : forums concernés et surcharges retirées / modifiées / ajoutées (avant → après)."""
    details = await _game_manager().resync_preview()
    return {"forums": len(details), "details": details}


class ProvisionRequest(BaseModel):
    # Reprendre un rôle ou un forum homonyme non rattaché : web-api ne l'autorise qu'aux admins.
    reuse_existing: bool = False


@app.post("/games/{key}/provision", dependencies=[Depends(_require_token)])
@_game_errors
async def game_provision(key: GameKey, req: Optional[ProvisionRequest] = None):
    cog = _game_manager()
    result = await cog.provision(key, reuse_existing=bool(req and req.reuse_existing))
    return {"role_id": str(result["role_id"]), "forum_id": str(result["forum_id"]),
            "command": result["command"], "created": list(result["created"]),
            "status": cog.status(key)}


@app.post("/games/{key}/archive", dependencies=[Depends(_require_token)])
@_game_errors
async def game_archive(key: GameKey):
    return {"status": await _game_manager().archive(key)}


@app.post("/games/{key}/unarchive", dependencies=[Depends(_require_token)])
@_game_errors
async def game_unarchive(key: GameKey):
    return {"status": await _game_manager().unarchive(key)}


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
