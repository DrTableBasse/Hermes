# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Project Overview

**Hermes** is a modular Discord bot + web platform for the SaucisseLand community. The v2 codebase uses a 4-container Docker stack. There is also legacy root-level code (`main.py`, `cogs/`, `utils/`) from v1 — prefer the `bot/` subdirectory for any new work.

---

## Quick Commands

```bash
# Start the full stack (recommended)
docker compose up --build

# Start only specific services
docker compose up db bot

# Run the bot locally (without Docker)
cd bot && pip install -r requirements.txt
python main.py

# Lint
flake8 .

# Tests
pytest
```

### Web frontend (Next.js)
```bash
cd web
npm install
npm run dev        # dev server on :3000
npm run build && npm start
```

---

## Architecture — Docker Stack

```
docker-compose.yml
├── db          PostgreSQL 15 (internal only)
├── bot         Discord bot + internal FastAPI on :8001
├── web-api     Public FastAPI on :8000
└── web         Next.js frontend on :3000
```

### Service responsibilities

**`bot/`** — Discord bot process  
- Connects to Discord, loads cogs, syncs slash commands  
- Runs an **internal FastAPI** (`bot/api.py`, port 8001) on the Docker network only — `web-api` calls it to trigger Discord actions (kick, ban, timeout, warn, command toggle)  
- Internal API is bearer-token protected via `BOT_API_TOKEN`

**`web-api/`** — Public REST API  
- Discord OAuth2 login (`web-api/auth.py` + `web-api/routes/auth.py`)  
- Routes: `auth`, `users`, `leaderboard`, `articles`, `tags`, `media`, `admin`  
- Calls `http://bot:8001` for Discord moderation actions  
- CORS allows only `localhost:3000` and `web:3000`

**`web/`** — Next.js frontend  
- TypeScript, Tailwind CSS, next-intl (fr/en)  
- Pages: articles, article editor, leaderboard, profile, admin panel  
- Auth via Discord OAuth2 redirect to `web-api`

---

## Bot — Cog System

Cogs live in `bot/cogs/{fun,moderation,system}/`. Auto-discovered by `bot/utils/constants.py::cogs_names()` — every `.py` file in those directories is loaded. No manual registration needed.

### Adding a command

1. Create `bot/cogs/<category>/my_command.py`
2. Implement `async def setup(bot): await bot.add_cog(MyCog(bot))`
3. Use `@command_enabled()` from `bot/utils/command_manager.py` to gate execution
4. Use `@administration_only()` from `bot/utils/decorators.py` for privileged commands
5. Restart the bot — cog loads and slash commands sync automatically

### Mandatory command pattern

```python
from utils.command_manager import command_enabled
from utils.decorators import administration_only

class MyCog(commands.Cog):
    @app_commands.command()
    @command_enabled()          # checks DB; responds ephemerally if disabled
    @administration_only()      # checks for ADMIN_ROLE_NAME role
    async def my_cmd(self, interaction: discord.Interaction):
        ...
```

`@command_enabled()` always queries the DB (cache bypassed) and sends an ephemeral error if the command is disabled. **Never skip this decorator.**

---

## Bot — Database Layer (`bot/utils/database.py`)

Global `asyncpg` pool shared across the process. Three manager singletons are initialized at import time:

| Manager | Purpose |
|---|---|
| `voice_manager` | Voice time tracking, member sync |
| `warn_manager` | Moderation warnings |
| `message_stats_manager` | Per-channel message counts |

**Rules:**
- Always `await` queries; never block the event loop
- Use the pool via `get_connection()` context manager — never open a new connection
- All DB-related code must run **after** `await init_database()` completes in `on_ready`

---

## Bot — Startup Order (critical)

`on_ready` must execute in this order:
1. `validate_config()`
2. `set_bot_instance(bot)` — wires bot into internal API
3. `await init_database()` + `await init_command_status_table()`
4. Member sync (`guild.chunk` → `voice_manager.sync_member`)
5. `await load_cogs()`
6. `bot.tree.sync()` — guild-scoped slash command sync

Anything that touches the DB or bot state must come after step 3.

---

## Bot — Logging (`bot/utils/logging.py`)

Structured logging via Discord embeds. Channel resolution priority:
- Specialized env var (e.g. `VOICE_LOG_CHANNEL_ID`) → falls back to `LOG_CHANNEL_ID`

Available functions: `log_command_usage`, `log_admin_action`, `log_voice_event`, `log_role_assignment`, `log_sanction`, `log_confession`

Use the `@log_command()` decorator to log after successful execution. Don't call logging functions manually unless the decorator doesn't fit.

---

## Environment Variables

Create a `.env` file at the repo root (used by Docker Compose and local runs).

| Variable | Required | Description |
|---|---|---|
| `DISCORD_TOKEN` | ✅ | Bot token |
| `GUILD_ID` | ✅ | Target guild ID |
| `BOT_CHANNEL_START` | ✅ | Startup message channel |
| `BOT_API_TOKEN` | ✅ | Shared secret between web-api and bot internal API |
| `PG_HOST` / `PG_PORT` / `PG_DB` / `PG_USER` / `PG_PASSWORD` | ✅ | PostgreSQL credentials |
| `DISCORD_CLIENT_ID` / `DISCORD_CLIENT_SECRET` | ✅ (web) | OAuth2 app credentials |
| `NEXT_PUBLIC_API_URL` | ✅ (web) | Public URL of web-api |
| `LOG_CHANNEL_ID` | ✅ | Default log channel |
| `VOICE_LOG_CHANNEL_ID` | | Voice-specific logs |
| `CONFESSION_CHANNEL_ID` | | Confession system |
| `ANIME_NEWS_CHANNEL_ID` | | Anime article feed |
| `ADMIN_ROLE_NAME` | | Role name for admin commands (default: `Administration`) |
| `AUTHORIZED_ROLES` | | Comma-separated moderation roles |
| `BLAGUES_API_TOKEN` | | Joke API |

---

## Key Design Constraints

- **Async only** — no blocking I/O anywhere in bot or web-api code
- **No shared mutable state** between the bot's async event loop and the internal API thread (the internal API runs uvicorn in a daemon thread via `threading.Thread`)
- **Slash commands are guild-scoped** — synced to `GUILD_ID` only, not globally
- **Root-level v1 code** (`main.py`, `cogs/`, `utils/`) is legacy; don't extend it
