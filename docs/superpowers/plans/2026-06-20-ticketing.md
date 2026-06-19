# Ticketing System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a bidirectional support ticketing system — tickets created on the web or via `/newticket` Discord command, with messages syncing in both directions in near real-time.

**Architecture:** The bot's internal API (`bot:8001`) is the bridge — `web-api` calls it to create Discord channels and relay messages, while the bot's `on_message` listener writes Discord messages directly to the DB. A new cog `ticket_manager.py` centralises all Discord-side logic (command + listener + channel helper).

**Tech Stack:** Python 3.11 + discord.py (bot), FastAPI + asyncpg (web-api), Next.js 14 + TypeScript + Tailwind (web), PostgreSQL 15 (DB)

## Global Constraints

- Async only — no blocking I/O in bot or web-api
- All Discord channel creation uses category ID `777139814599491584`
- Admin role name comes from env var `ADMIN_ROLE_NAME` (default: `Administration`)
- Bot API calls from web-api use `BOT_API_URL` env var (default: `http://bot:8001`) with bearer token `BOT_API_TOKEN`
- One open ticket per user enforced at DB level (partial unique index) AND in application logic
- No tests exist in this project — replace test steps with manual verification via `docker compose logs` and browser inspection
- Follow existing patterns: `_bot()` helper in web-api, `request<T>()` in `api.ts`, `get<T>()` in `server-api.ts`

---

### Task 1: DB Migration

**Files:**
- Create: `db/migrations/003_tickets.sql`

**Interfaces:**
- Produces: tables `tickets` and `ticket_messages` consumed by all subsequent tasks

- [ ] **Step 1: Create the migration file**

```sql
-- db/migrations/003_tickets.sql

CREATE TABLE tickets (
    id                 SERIAL PRIMARY KEY,
    user_id            BIGINT NOT NULL,
    title              TEXT NOT NULL,
    status             TEXT NOT NULL DEFAULT 'open',  -- open | resolved | closed
    discord_channel_id BIGINT,
    created_at         TIMESTAMPTZ DEFAULT NOW(),
    closed_at          TIMESTAMPTZ,
    created_by_admin   BOOLEAN DEFAULT FALSE
);

-- Enforce one open ticket per user at DB level
CREATE UNIQUE INDEX one_open_ticket_per_user
    ON tickets (user_id)
    WHERE (status = 'open');

CREATE TABLE ticket_messages (
    id          SERIAL PRIMARY KEY,
    ticket_id   INTEGER NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    author_id   BIGINT NOT NULL,
    author_name TEXT NOT NULL,
    content     TEXT NOT NULL,
    source      TEXT NOT NULL DEFAULT 'web',  -- 'web' | 'discord'
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX ON tickets(user_id);
CREATE INDEX ON tickets(status);
CREATE INDEX ON ticket_messages(ticket_id);
```

- [ ] **Step 2: Apply the migration**

```bash
docker compose exec db psql -U $PG_USER -d $PG_DB -f /dev/stdin < db/migrations/003_tickets.sql
```

Expected: `CREATE TABLE`, `CREATE INDEX` (×5 lines), no errors.

- [ ] **Step 3: Verify tables exist**

```bash
docker compose exec db psql -U $PG_USER -d $PG_DB -c "\dt tickets" -c "\dt ticket_messages"
```

Expected: both tables listed.

- [ ] **Step 4: Commit**

```bash
git add db/migrations/003_tickets.sql
git commit -m "feat(db): tables tickets + ticket_messages"
```

---

### Task 2: Bot — cog ticket_manager.py

**Files:**
- Create: `bot/cogs/system/ticket_manager.py`

**Interfaces:**
- Consumes: `db_manager` from `utils/database.py`, `command_enabled` from `utils/command_manager.py`
- Produces:
  - `TicketManagerCog.create_ticket_channel(guild, user, ticket_id, title) -> int` — used by Task 3
  - `TicketManagerCog._ticket_channels: dict[int, int]` — `discord_channel_id -> ticket_id` cache, used by Task 3

- [ ] **Step 1: Create the cog file**

```python
# bot/cogs/system/ticket_manager.py
"""Ticket manager — /newticket command + Discord ↔ web sync listener."""
import os
import logging
import discord
from discord import app_commands
from discord.ext import commands
from utils.database import db_manager
from utils.command_manager import command_enabled

logger = logging.getLogger(__name__)
TICKET_CATEGORY_ID = 777139814599491584


class TicketManagerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._ticket_channels: dict[int, int] = {}  # discord_channel_id -> ticket_id

    async def cog_load(self):
        """Load active ticket channels from DB into memory cache on startup."""
        rows = await db_manager.fetch(
            "SELECT id, discord_channel_id FROM tickets "
            "WHERE discord_channel_id IS NOT NULL AND status = 'open'"
        )
        self._ticket_channels = {row["discord_channel_id"]: row["id"] for row in rows}
        logger.info("TicketManagerCog: %d salon(s) ticket actif(s) chargé(s)", len(self._ticket_channels))

    @app_commands.command(name="newticket", description="Ouvrir un ticket de support")
    @command_enabled(guild_specific=True)
    async def newticket(self, interaction: discord.Interaction, titre: str):
        await interaction.response.defer(ephemeral=True)

        existing = await db_manager.fetchval(
            "SELECT id FROM tickets WHERE user_id = $1 AND status = 'open'",
            interaction.user.id,
        )
        if existing:
            await interaction.followup.send(
                f"❌ Tu as déjà un ticket ouvert (#{existing}). "
                "Ferme-le avant d'en créer un nouveau.",
                ephemeral=True,
            )
            return

        ticket_id = await db_manager.fetchval(
            "INSERT INTO tickets (user_id, title) VALUES ($1, $2) RETURNING id",
            interaction.user.id,
            titre,
        )

        channel_id = await self.create_ticket_channel(
            interaction.guild, interaction.user, ticket_id, titre
        )

        await db_manager.execute(
            "UPDATE tickets SET discord_channel_id = $1 WHERE id = $2",
            channel_id,
            ticket_id,
        )
        self._ticket_channels[channel_id] = ticket_id

        await interaction.followup.send(
            f"✅ Ticket **#{ticket_id}** créé ! → <#{channel_id}>",
            ephemeral=True,
        )

    async def create_ticket_channel(
        self,
        guild: discord.Guild,
        user: discord.Member | discord.User,
        ticket_id: int,
        title: str,
    ) -> int:
        """Create a ticket text channel in the ticket category. Returns the channel ID."""
        category = guild.get_channel(TICKET_CATEGORY_ID)
        admin_role_name = os.getenv("ADMIN_ROLE_NAME", "Administration")
        admin_role = discord.utils.get(guild.roles, name=admin_role_name)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            guild.me: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, manage_channels=True
            ),
        }
        if admin_role:
            overwrites[admin_role] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True
            )

        safe_name = "".join(
            c if c.isalnum() or c == "-" else "-"
            for c in user.display_name.lower()
        )[:20].strip("-")
        channel = await guild.create_text_channel(
            name=f"ticket-{safe_name}-{ticket_id}",
            category=category,
            overwrites=overwrites,
            reason=f"Ticket #{ticket_id}",
        )

        embed = discord.Embed(
            title=f"🎫 Ticket #{ticket_id} — {title}",
            description=(
                f"Ouvert par {user.mention}\n"
                "Répondez ici ou sur le site web."
            ),
            color=0x57F287,
        )
        embed.set_footer(text="Hermes · SaucisseLand")
        await channel.send(embed=embed)
        return channel.id

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        ticket_id = self._ticket_channels.get(message.channel.id)
        if ticket_id is None:
            return

        status = await db_manager.fetchval(
            "SELECT status FROM tickets WHERE id = $1", ticket_id
        )
        if status != "open":
            return

        await db_manager.execute(
            """INSERT INTO ticket_messages
                   (ticket_id, author_id, author_name, content, source)
               VALUES ($1, $2, $3, $4, 'discord')""",
            ticket_id,
            message.author.id,
            message.author.display_name,
            message.content,
        )


async def setup(bot):
    await bot.add_cog(TicketManagerCog(bot))
```

- [ ] **Step 2: Restart the bot and verify the cog loads**

```bash
docker compose restart bot
docker compose logs bot --tail=30
```

Expected log line: `TicketManagerCog: 0 salon(s) ticket actif(s) chargé(s)`
Also check that `/newticket` appears in slash commands on Discord (may take a few seconds to sync).

- [ ] **Step 3: Smoke test via Discord**

In any Discord channel, type `/newticket titre:Test init`.
Expected: ephemeral reply "✅ Ticket #1 créé ! → #ticket-…", new channel created in the ticket category.

- [ ] **Step 4: Commit**

```bash
git add bot/cogs/system/ticket_manager.py
git commit -m "feat(bot): cog ticket_manager — /newticket + on_message sync"
```

---

### Task 3: Bot API — ticket endpoints

**Files:**
- Modify: `bot/api.py` (add after the last `@app.post` block, before `run_api()`)

**Interfaces:**
- Consumes: `TicketManagerCog.create_ticket_channel()`, `TicketManagerCog._ticket_channels` (Task 2)
- Consumes: `_require_token`, `_get_bot`, `_get_guild`, `_get_member` already defined in `api.py`
- Produces:
  - `POST /tickets/create` → `{ discord_channel_id: int }`
  - `POST /tickets/{ticket_id}/message` → `{ success: true }`
  - `POST /tickets/{ticket_id}/close` → `{ success: true }`

- [ ] **Step 1: Add Pydantic models and three endpoints to `bot/api.py`**

Open `bot/api.py` and add the following block just before the `def run_api():` function at the bottom:

```python
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
```

- [ ] **Step 2: Rebuild and verify endpoints are registered**

```bash
docker compose up --build bot -d
docker compose logs bot --tail=20
```

Expected: no import errors, bot connects normally.

- [ ] **Step 3: Smoke test the create endpoint**

```bash
docker compose exec web-api curl -s -X POST http://bot:8001/tickets/create \
  -H "Authorization: Bearer $BOT_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"user_id": 123, "username": "test", "ticket_id": 99, "title": "Test API"}'
```

Expected: `{"discord_channel_id": <some_id>}` (or an error if user 123 isn't a guild member — that's fine, proves the endpoint is reachable).

- [ ] **Step 4: Commit**

```bash
git add bot/api.py
git commit -m "feat(bot): endpoints /tickets/create, /message, /close"
```

---

### Task 4: web-api — tickets routes

**Files:**
- Create: `web-api/routes/tickets.py`
- Modify: `web-api/main.py` (add import + `include_router`)

**Interfaces:**
- Consumes: `db` module, `get_current_user`, `require_admin` from `middleware/auth_middleware.py`
- Consumes: bot endpoints from Task 3 via `_bot()` helper
- Produces: REST API at `/tickets` consumed by Task 5 and Task 6

- [ ] **Step 1: Create `web-api/routes/tickets.py`**

```python
# web-api/routes/tickets.py
"""Support ticket routes."""
import logging
import os

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import db as db
from middleware.auth_middleware import get_current_user, require_admin

router = APIRouter(prefix="/tickets", tags=["tickets"])
logger = logging.getLogger(__name__)

BOT_API_URL   = os.getenv("BOT_API_URL", "http://bot:8001")
BOT_API_TOKEN = os.getenv("BOT_API_TOKEN", "")


def _bot_headers():
    return {"Authorization": f"Bearer {BOT_API_TOKEN}"}


async def _bot(method: str, path: str, **kwargs):
    async with httpx.AsyncClient(timeout=10) as client:
        r = await getattr(client, method)(
            f"{BOT_API_URL}{path}", headers=_bot_headers(), **kwargs
        )
        if r.status_code >= 400:
            try:
                detail = r.json().get("detail", r.text)
            except Exception:
                detail = r.text
            raise HTTPException(status_code=r.status_code, detail=detail)
        return r.json()


class TicketCreate(BaseModel):
    title: str


class TicketAdminCreate(BaseModel):
    user_id: str
    title: str


class MessageCreate(BaseModel):
    content: str


def _serialize_ticket(t) -> dict:
    return {
        "id":                 t["id"],
        "user_id":            str(t["user_id"]),
        "title":              t["title"],
        "status":             t["status"],
        "discord_channel_id": str(t["discord_channel_id"]) if t["discord_channel_id"] else None,
        "created_at":         t["created_at"].isoformat() if t["created_at"] else None,
        "closed_at":          t["closed_at"].isoformat() if t["closed_at"] else None,
        "created_by_admin":   t["created_by_admin"],
        "username":           t.get("username"),
        "discord_avatar":     t.get("discord_avatar"),
    }


def _serialize_message(m) -> dict:
    return {
        "id":          m["id"],
        "ticket_id":   m["ticket_id"],
        "author_id":   str(m["author_id"]),
        "author_name": m["author_name"],
        "content":     m["content"],
        "source":      m["source"],
        "created_at":  m["created_at"].isoformat() if m["created_at"] else None,
    }


async def _get_username(user_id: int) -> str:
    row = await db.fetchrow(
        "SELECT COALESCE(nickname, username) AS name FROM user_voice_data WHERE user_id = $1",
        user_id,
    )
    return row["name"] if row else str(user_id)


@router.post("", status_code=201)
async def create_ticket(body: TicketCreate, user: dict = Depends(get_current_user)):
    user_id = int(user["sub"])
    existing = await db.fetchval(
        "SELECT id FROM tickets WHERE user_id = $1 AND status = 'open'", user_id
    )
    if existing:
        raise HTTPException(status_code=409, detail="Tu as déjà un ticket ouvert.")

    username = await _get_username(user_id)
    ticket_id = await db.fetchval(
        "INSERT INTO tickets (user_id, title) VALUES ($1, $2) RETURNING id",
        user_id,
        body.title,
    )

    try:
        result = await _bot("post", "/tickets/create", json={
            "user_id": user_id, "username": username,
            "ticket_id": ticket_id, "title": body.title,
        })
        channel_id = result.get("discord_channel_id")
        if channel_id:
            await db.execute(
                "UPDATE tickets SET discord_channel_id = $1 WHERE id = $2",
                int(channel_id), ticket_id,
            )
    except Exception as e:
        logger.warning("Ticket #%s: création salon Discord échouée: %s", ticket_id, e)

    ticket = await db.fetchrow("SELECT * FROM tickets WHERE id = $1", ticket_id)
    return _serialize_ticket(ticket)


@router.post("/admin", status_code=201)
async def create_ticket_admin(body: TicketAdminCreate, user: dict = Depends(get_current_user)):
    require_admin(user)
    target_id = int(body.user_id)
    existing = await db.fetchval(
        "SELECT id FROM tickets WHERE user_id = $1 AND status = 'open'", target_id
    )
    if existing:
        raise HTTPException(status_code=409, detail="Cet utilisateur a déjà un ticket ouvert.")

    username = await _get_username(target_id)
    ticket_id = await db.fetchval(
        "INSERT INTO tickets (user_id, title, created_by_admin) VALUES ($1, $2, TRUE) RETURNING id",
        target_id, body.title,
    )

    try:
        result = await _bot("post", "/tickets/create", json={
            "user_id": target_id, "username": username,
            "ticket_id": ticket_id, "title": body.title,
        })
        channel_id = result.get("discord_channel_id")
        if channel_id:
            await db.execute(
                "UPDATE tickets SET discord_channel_id = $1 WHERE id = $2",
                int(channel_id), ticket_id,
            )
    except Exception as e:
        logger.warning("Ticket #%s: création salon Discord échouée: %s", ticket_id, e)

    ticket = await db.fetchrow("SELECT * FROM tickets WHERE id = $1", ticket_id)
    return _serialize_ticket(ticket)


@router.get("")
async def list_tickets(user: dict = Depends(get_current_user)):
    user_id = int(user["sub"])
    if user.get("is_admin"):
        rows = await db.fetch(
            """SELECT t.*, v.username, v.discord_avatar
               FROM tickets t
               LEFT JOIN user_voice_data v ON t.user_id = v.user_id
               ORDER BY
                 CASE t.status WHEN 'open' THEN 0 WHEN 'resolved' THEN 1 ELSE 2 END,
                 t.created_at DESC"""
        )
    else:
        rows = await db.fetch(
            "SELECT * FROM tickets WHERE user_id = $1 ORDER BY created_at DESC",
            user_id,
        )
    return {"tickets": [_serialize_ticket(r) for r in rows]}


@router.get("/{ticket_id}")
async def get_ticket(ticket_id: int, user: dict = Depends(get_current_user)):
    user_id = int(user["sub"])
    ticket = await db.fetchrow("SELECT * FROM tickets WHERE id = $1", ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket introuvable")
    if not user.get("is_admin") and ticket["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Accès refusé")
    messages = await db.fetch(
        "SELECT * FROM ticket_messages WHERE ticket_id = $1 ORDER BY created_at ASC",
        ticket_id,
    )
    return {
        **_serialize_ticket(ticket),
        "messages": [_serialize_message(m) for m in messages],
    }


@router.post("/{ticket_id}/message")
async def send_message(
    ticket_id: int, body: MessageCreate, user: dict = Depends(get_current_user)
):
    user_id = int(user["sub"])
    ticket = await db.fetchrow("SELECT * FROM tickets WHERE id = $1", ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket introuvable")
    if not user.get("is_admin") and ticket["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Accès refusé")
    if ticket["status"] != "open":
        raise HTTPException(status_code=409, detail="Ce ticket est fermé.")

    author_name = await _get_username(user_id)
    await db.execute(
        """INSERT INTO ticket_messages
               (ticket_id, author_id, author_name, content, source)
           VALUES ($1, $2, $3, $4, 'web')""",
        ticket_id, user_id, author_name, body.content,
    )

    try:
        await _bot("post", f"/tickets/{ticket_id}/message", json={
            "content": body.content, "author_name": author_name,
        })
    except Exception as e:
        logger.warning("Ticket #%s: relay Discord échoué: %s", ticket_id, e)

    return {"success": True}


@router.post("/{ticket_id}/resolve")
async def resolve_ticket(ticket_id: int, user: dict = Depends(get_current_user)):
    user_id = int(user["sub"])
    ticket = await db.fetchrow("SELECT * FROM tickets WHERE id = $1", ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket introuvable")
    if ticket["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Accès refusé")
    if ticket["status"] != "open":
        raise HTTPException(status_code=409, detail="Ce ticket n'est pas ouvert.")
    await db.execute(
        "UPDATE tickets SET status = 'resolved', closed_at = NOW() WHERE id = $1",
        ticket_id,
    )
    return {"success": True}


@router.post("/{ticket_id}/close")
async def close_ticket(ticket_id: int, user: dict = Depends(get_current_user)):
    require_admin(user)
    ticket = await db.fetchrow("SELECT * FROM tickets WHERE id = $1", ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket introuvable")
    if ticket["status"] == "closed":
        raise HTTPException(status_code=409, detail="Ticket déjà fermé.")
    await db.execute(
        "UPDATE tickets SET status = 'closed', closed_at = NOW() WHERE id = $1",
        ticket_id,
    )
    try:
        await _bot("post", f"/tickets/{ticket_id}/close", json={})
    except Exception as e:
        logger.warning("Ticket #%s: fermeture Discord échouée: %s", ticket_id, e)
    return {"success": True}
```

- [ ] **Step 2: Register the router in `web-api/main.py`**

Add to the imports block:
```python
from routes import auth, users, leaderboard, articles, tags, media, admin
from routes import xp, notifications, endorsements, activity, quests, comments, automod_api, tickets
```

Add after the last `app.include_router(...)` call:
```python
app.include_router(tickets.router)
```

- [ ] **Step 3: Rebuild web-api and verify**

```bash
docker compose up --build web-api -d
docker compose logs web-api --tail=20
```

Expected: FastAPI starts, no import errors. Routes listed include `/tickets`.

- [ ] **Step 4: Smoke test via curl**

```bash
# From inside web-api container (substitute a real session token):
docker compose exec web-api curl -s http://localhost:8000/tickets \
  -H "Cookie: better-auth.session_token=<your_token>"
```

Expected: `{"tickets": []}` (empty list, not a 500 error).

- [ ] **Step 5: Commit**

```bash
git add web-api/routes/tickets.py web-api/main.py
git commit -m "feat(web-api): routes /tickets — CRUD + Discord bridge"
```

---

### Task 5: Web — types, server helpers, client API

**Files:**
- Modify: `web/src/lib/api.ts` (add `tickets` namespace + types)
- Modify: `web/src/lib/server-api.ts` (add server-side helpers)

**Interfaces:**
- Produces:
  - `Ticket`, `TicketMessage` TypeScript types
  - `api.tickets.*` client-side methods
  - `serverGetMyTickets(token)`, `serverGetTicket(id, token)`, `serverListAllTickets(token)` server-side helpers

- [ ] **Step 1: Add types and client API to `web/src/lib/api.ts`**

Add at the end of the types section (before `export const api = {`):

```typescript
export interface Ticket {
  id: number
  user_id: string
  title: string
  status: 'open' | 'resolved' | 'closed'
  discord_channel_id: string | null
  created_at: string
  closed_at: string | null
  created_by_admin: boolean
  username?: string
  discord_avatar?: string | null
}

export interface TicketMessage {
  id: number
  ticket_id: number
  author_id: string
  author_name: string
  content: string
  source: 'web' | 'discord'
  created_at: string
}

export interface TicketDetail extends Ticket {
  messages: TicketMessage[]
}
```

Add `tickets` namespace inside the `export const api = {` object (after the last existing namespace):

```typescript
  tickets: {
    list:    ()                          => request<{ tickets: Ticket[] }>('/tickets'),
    get:     (id: number)               => request<TicketDetail>(`/tickets/${id}`),
    create:  (title: string)            => request<Ticket>('/tickets', { method: 'POST', body: JSON.stringify({ title }) }),
    message: (id: number, content: string) =>
      request<{ success: boolean }>(`/tickets/${id}/message`, { method: 'POST', body: JSON.stringify({ content }) }),
    resolve: (id: number)               => request<{ success: boolean }>(`/tickets/${id}/resolve`, { method: 'POST' }),
    close:   (id: number)               => request<{ success: boolean }>(`/tickets/${id}/close`,   { method: 'POST' }),
    adminCreate: (user_id: string, title: string) =>
      request<Ticket>('/tickets/admin', { method: 'POST', body: JSON.stringify({ user_id, title }) }),
  },
```

- [ ] **Step 2: Add server-side helpers to `web/src/lib/server-api.ts`**

Add at the end of the file:

```typescript
// ── Tickets ───────────────────────────────────────────────────────────────────

import type { Ticket, TicketDetail } from './api'

export async function serverGetMyTickets(token: string): Promise<Ticket[]> {
  const data = await get<{ tickets: Ticket[] }>('/tickets', token)
  return data.tickets
}

export async function serverListAllTickets(token: string): Promise<Ticket[]> {
  const data = await get<{ tickets: Ticket[] }>('/tickets', token)
  return data.tickets
}

export async function serverGetTicket(id: number, token: string): Promise<TicketDetail> {
  return get<TicketDetail>(`/tickets/${id}`, token)
}
```

- [ ] **Step 3: Build check**

```bash
cd web && npm run build 2>&1 | tail -20
```

Expected: build succeeds (or only pre-existing errors — no new TypeScript errors from our additions).

- [ ] **Step 4: Commit**

```bash
git add web/src/lib/api.ts web/src/lib/server-api.ts
git commit -m "feat(web): types + API helpers pour les tickets"
```

---

### Task 6: Web — admin tickets page + ticket detail page

**Files:**
- Create: `web/src/app/[locale]/tickets/page.tsx`
- Create: `web/src/app/[locale]/tickets/[id]/page.tsx`
- Create: `web/src/app/[locale]/tickets/[id]/TicketChat.tsx` (client component for message input)

**Interfaces:**
- Consumes: `serverListAllTickets`, `serverGetTicket` (Task 5), `api.tickets.*` (Task 5)
- Consumes: `auth`, `headers` from Next.js/BetterAuth (same pattern as profile page)

- [ ] **Step 1: Create the admin tickets list page**

```typescript
// web/src/app/[locale]/tickets/page.tsx
import { headers } from 'next/headers'
import Link from 'next/link'
import { redirect } from 'next/navigation'
import { auth } from '@/lib/auth'
import { serverListAllTickets } from '@/lib/server-api'
import type { Ticket } from '@/lib/api'

const STATUS_LABEL: Record<string, string> = {
  open:     '🟢 Ouvert',
  resolved: '🟡 Résolu',
  closed:   '⚪ Fermé',
}
const STATUS_CLASS: Record<string, string> = {
  open:     'text-green-400',
  resolved: 'text-yellow-400',
  closed:   'text-muted-foreground',
}

export default async function TicketsAdminPage({
  params,
}: {
  params: Promise<{ locale: string }>
}) {
  const { locale } = await params
  const session = await auth.api.getSession({ headers: await headers() })
  const u = session?.user as any
  if (!u) redirect(`/${locale}/login`)
  if (!u.isAdmin) redirect(`/${locale}`)

  const token = (session!.session as any).token as string
  let tickets: Ticket[] = []
  try { tickets = await serverListAllTickets(token) } catch {}

  return (
    <div className="container mx-auto px-4 py-12 max-w-4xl">
      <h1 className="text-3xl font-extrabold tracking-tight mb-8">🎫 Tickets</h1>

      {tickets.length === 0 ? (
        <p className="text-muted-foreground text-center py-12">Aucun ticket.</p>
      ) : (
        <div className="space-y-3">
          {tickets.map((t) => (
            <Link
              key={t.id}
              href={`/${locale}/tickets/${t.id}`}
              className="glass-card p-4 flex items-center gap-4 hover:bg-accent/40 transition-colors block"
            >
              <span className="text-lg font-bold text-muted-foreground w-10 shrink-0">
                #{t.id}
              </span>
              <div className="flex-1 min-w-0">
                <p className="font-semibold truncate">{t.title}</p>
                <p className="text-xs text-muted-foreground">
                  {t.username ?? t.user_id} · {new Date(t.created_at).toLocaleDateString('fr-FR')}
                </p>
              </div>
              <span className={`text-sm font-medium shrink-0 ${STATUS_CLASS[t.status]}`}>
                {STATUS_LABEL[t.status]}
              </span>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Create the client chat component**

```typescript
// web/src/app/[locale]/tickets/[id]/TicketChat.tsx
'use client'
import { useState } from 'react'
import { api } from '@/lib/api'
import type { TicketDetail, TicketMessage } from '@/lib/api'

function SourceBadge({ source }: { source: 'web' | 'discord' }) {
  return (
    <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${
      source === 'discord'
        ? 'bg-indigo-500/20 text-indigo-300'
        : 'bg-emerald-500/20 text-emerald-300'
    }`}>
      {source === 'discord' ? '🎮 Discord' : '🌐 Web'}
    </span>
  )
}

export default function TicketChat({
  ticket,
  isAdmin,
  locale,
}: {
  ticket: TicketDetail
  isAdmin: boolean
  locale: string
}) {
  const [messages, setMessages] = useState<TicketMessage[]>(ticket.messages)
  const [content, setContent]   = useState('')
  const [sending, setSending]   = useState(false)
  const [status, setStatus]     = useState(ticket.status)
  const [error, setError]       = useState<string | null>(null)

  const isClosed = status !== 'open'

  async function sendMessage(e: React.FormEvent) {
    e.preventDefault()
    if (!content.trim() || sending) return
    setSending(true)
    setError(null)
    try {
      await api.tickets.message(ticket.id, content.trim())
      // Optimistic: reload messages from server
      const updated = await api.tickets.get(ticket.id)
      setMessages(updated.messages)
      setContent('')
    } catch (err: any) {
      setError(err.message ?? 'Erreur lors de l\'envoi')
    } finally {
      setSending(false)
    }
  }

  async function handleResolve() {
    try {
      await api.tickets.resolve(ticket.id)
      setStatus('resolved')
    } catch (err: any) {
      setError(err.message)
    }
  }

  async function handleClose() {
    try {
      await api.tickets.close(ticket.id)
      setStatus('closed')
    } catch (err: any) {
      setError(err.message)
    }
  }

  return (
    <div className="space-y-4">
      {/* Message thread */}
      <div className="space-y-3 max-h-[60vh] overflow-y-auto">
        {messages.length === 0 && (
          <p className="text-muted-foreground text-center py-6">Aucun message pour l'instant.</p>
        )}
        {messages.map((m) => (
          <div key={m.id} className="glass-card p-4">
            <div className="flex items-center gap-2 mb-1">
              <span className="font-semibold text-sm">{m.author_name}</span>
              <SourceBadge source={m.source} />
              <span className="text-xs text-muted-foreground ml-auto">
                {new Date(m.created_at).toLocaleString('fr-FR')}
              </span>
            </div>
            <p className="text-sm whitespace-pre-wrap">{m.content}</p>
          </div>
        ))}
      </div>

      {/* Error */}
      {error && <p className="text-red-400 text-sm">{error}</p>}

      {/* Reply form */}
      {!isClosed && (
        <form onSubmit={sendMessage} className="flex gap-2">
          <input
            className="flex-1 rounded-md border border-border bg-background px-3 py-2 text-sm"
            placeholder="Votre message..."
            value={content}
            onChange={(e) => setContent(e.target.value)}
            disabled={sending}
          />
          <button
            type="submit"
            disabled={sending || !content.trim()}
            className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
          >
            {sending ? '...' : 'Envoyer'}
          </button>
        </form>
      )}

      {/* Actions */}
      <div className="flex gap-3 pt-2">
        {!isClosed && !isAdmin && (
          <button
            onClick={handleResolve}
            className="rounded-md border border-yellow-500/50 px-4 py-2 text-sm text-yellow-400 hover:bg-yellow-500/10"
          >
            ✅ Marquer comme résolu
          </button>
        )}
        {!isClosed && isAdmin && (
          <button
            onClick={handleClose}
            className="rounded-md border border-red-500/50 px-4 py-2 text-sm text-red-400 hover:bg-red-500/10"
          >
            🔒 Fermer définitivement
          </button>
        )}
        {isClosed && (
          <p className="text-muted-foreground text-sm">
            Ce ticket est {status === 'resolved' ? 'résolu' : 'fermé'}.
          </p>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Create the ticket detail page**

```typescript
// web/src/app/[locale]/tickets/[id]/page.tsx
import { headers } from 'next/headers'
import { notFound, redirect } from 'next/navigation'
import { auth } from '@/lib/auth'
import { serverGetTicket } from '@/lib/server-api'
import TicketChat from './TicketChat'

const STATUS_LABEL: Record<string, string> = {
  open:     '🟢 Ouvert',
  resolved: '🟡 Résolu',
  closed:   '⚪ Fermé',
}

export default async function TicketDetailPage({
  params,
}: {
  params: Promise<{ locale: string; id: string }>
}) {
  const { locale, id } = await params
  const ticketId = Number(id)
  if (isNaN(ticketId)) notFound()

  const session = await auth.api.getSession({ headers: await headers() })
  const u = session?.user as any
  if (!u) redirect(`/${locale}/login`)

  const token = (session!.session as any).token as string
  let ticket
  try {
    ticket = await serverGetTicket(ticketId, token)
  } catch {
    notFound()
  }

  const isAdmin = !!u.isAdmin

  return (
    <div className="container mx-auto px-4 py-12 max-w-3xl">
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <h1 className="text-2xl font-extrabold tracking-tight">
            🎫 Ticket #{ticket.id}
          </h1>
          <span className="text-sm font-medium text-muted-foreground">
            {STATUS_LABEL[ticket.status]}
          </span>
        </div>
        <p className="text-lg text-muted-foreground">{ticket.title}</p>
        <p className="text-xs text-muted-foreground mt-1">
          Ouvert le {new Date(ticket.created_at).toLocaleDateString('fr-FR')}
          {ticket.created_by_admin && ' · créé par un admin'}
        </p>
      </div>

      <TicketChat ticket={ticket} isAdmin={isAdmin} locale={locale} />
    </div>
  )
}
```

- [ ] **Step 4: Build and smoke test**

```bash
cd web && npm run build 2>&1 | tail -20
```

Then start the stack and navigate to `/fr/tickets` (as admin) and `/fr/tickets/1` — verify pages load without errors.

- [ ] **Step 5: Commit**

```bash
git add web/src/app/\[locale\]/tickets/
git commit -m "feat(web): page admin /tickets + page détail /tickets/[id]"
```

---

### Task 7: Web — profile tickets tab

**Files:**
- Create: `web/src/app/[locale]/tickets/TicketSection.tsx` (client component, reusable)
- Modify: `web/src/app/[locale]/profile/page.tsx`

**Interfaces:**
- Consumes: `serverGetMyTickets` (Task 5), `api.tickets.create` (Task 5)
- Consumes: existing profile page patterns (server component, `session`, `token`)

- [ ] **Step 1: Create the reusable TicketSection client component**

```typescript
// web/src/app/[locale]/tickets/TicketSection.tsx
'use client'
import { useState } from 'react'
import Link from 'next/link'
import { api } from '@/lib/api'
import type { Ticket } from '@/lib/api'

const STATUS_LABEL: Record<string, string> = {
  open:     '🟢 Ouvert',
  resolved: '🟡 Résolu',
  closed:   '⚪ Fermé',
}

export default function TicketSection({
  initialTickets,
  locale,
}: {
  initialTickets: Ticket[]
  locale: string
}) {
  const [tickets, setTickets]  = useState<Ticket[]>(initialTickets)
  const [title, setTitle]      = useState('')
  const [creating, setCreating] = useState(false)
  const [error, setError]      = useState<string | null>(null)

  const openTicket = tickets.find((t) => t.status === 'open')

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    if (!title.trim() || creating) return
    setCreating(true)
    setError(null)
    try {
      const ticket = await api.tickets.create(title.trim())
      setTickets((prev) => [ticket, ...prev])
      setTitle('')
    } catch (err: any) {
      setError(err.message ?? 'Erreur lors de la création')
    } finally {
      setCreating(false)
    }
  }

  return (
    <section>
      <h2 className="text-xl font-bold mb-5">🎫 Tickets</h2>

      {/* Create form — only if no open ticket */}
      {!openTicket && (
        <form onSubmit={handleCreate} className="glass-card p-4 mb-4 flex gap-2">
          <input
            className="flex-1 rounded-md border border-border bg-background px-3 py-2 text-sm"
            placeholder="Décrivez votre problème en quelques mots..."
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            disabled={creating}
          />
          <button
            type="submit"
            disabled={creating || !title.trim()}
            className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
          >
            {creating ? '...' : 'Ouvrir un ticket'}
          </button>
        </form>
      )}

      {error && <p className="text-red-400 text-sm mb-3">{error}</p>}

      {/* Ticket list */}
      {tickets.length === 0 ? (
        <p className="text-muted-foreground text-sm">Aucun ticket pour le moment.</p>
      ) : (
        <div className="space-y-2">
          {tickets.map((t) => (
            <Link
              key={t.id}
              href={`/${locale}/tickets/${t.id}`}
              className="glass-card p-3 flex items-center gap-3 hover:bg-accent/40 transition-colors block"
            >
              <span className="text-sm text-muted-foreground w-8 shrink-0">#{t.id}</span>
              <span className="flex-1 text-sm font-medium truncate">{t.title}</span>
              <span className="text-xs shrink-0">{STATUS_LABEL[t.status]}</span>
            </Link>
          ))}
        </div>
      )}
    </section>
  )
}
```

- [ ] **Step 2: Add tickets section to `web/src/app/[locale]/profile/page.tsx`**

Add the import at the top:
```typescript
import TicketSection from '../tickets/TicketSection'
import { serverGetMyTickets } from '@/lib/server-api'
import type { Ticket } from '@/lib/api'
```

Add data fetching after the existing `allAchievements` try/catch block:
```typescript
let myTickets: Ticket[] = []
try { myTickets = await serverGetMyTickets(token) } catch {}
```

Add the section before the closing `</div>` of the page, after the achievements section:
```tsx
{/* Tickets */}
<section className="mt-12">
  <TicketSection initialTickets={myTickets} locale={locale} />
</section>
```

- [ ] **Step 3: Build check**

```bash
cd web && npm run build 2>&1 | tail -20
```

Expected: build succeeds with no new TypeScript errors.

- [ ] **Step 4: Manual verification**

Start the full stack with `docker compose up`. Navigate to `/fr/profile` as a logged-in user:
- Should see a "🎫 Tickets" section with a creation form
- Create a ticket → form disappears, ticket appears in the list, Discord channel created in ticket category
- Click the ticket → detail page opens, can send messages
- Messages sent from web appear in Discord; messages typed in Discord appear on next page load

As admin, navigate to `/fr/tickets` → all tickets listed.

- [ ] **Step 5: Commit**

```bash
git add web/src/app/\[locale\]/tickets/TicketSection.tsx web/src/app/\[locale\]/profile/page.tsx
git commit -m "feat(web): TicketSection dans le profil utilisateur"
```

---

## Summary

| Task | Deliverable | Key files |
|------|-------------|-----------|
| 1 | DB tables | `db/migrations/003_tickets.sql` |
| 2 | Bot cog + `/newticket` command | `bot/cogs/system/ticket_manager.py` |
| 3 | Bot internal API endpoints | `bot/api.py` |
| 4 | web-api REST routes | `web-api/routes/tickets.py`, `web-api/main.py` |
| 5 | Web types + API helpers | `web/src/lib/api.ts`, `web/src/lib/server-api.ts` |
| 6 | Admin list + detail pages | `web/src/app/[locale]/tickets/` |
| 7 | Profile tickets tab | `web/src/app/[locale]/tickets/TicketSection.tsx`, `profile/page.tsx` |
