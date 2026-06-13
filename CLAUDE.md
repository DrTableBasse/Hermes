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
```

### Web frontend (Next.js)
```bash
cd web
npm install
npm run dev        # dev server on :3000
npm run build && npm start
```

### Web API (FastAPI)
```bash
cd web-api && pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

There are no automated tests in this project (no pytest/jest configs).

---

## Architecture — Docker Stack

```
compose.yml
├── db          PostgreSQL 15 (internal only)
├── bot         Discord bot + internal FastAPI on :8001
├── web-api     FastAPI on :8000 (Docker-internal; proxied by Next.js)
└── web         Next.js frontend on :3000
```

### Service responsibilities

**`bot/`** — Discord bot process
- Connects to Discord, loads cogs, syncs slash commands
- Runs an **internal FastAPI** (`bot/api.py`, port 8001) on the Docker network only — `web-api` calls it to trigger Discord actions (kick, ban, timeout, warn, command toggle)
- Internal API is bearer-token protected via `BOT_API_TOKEN`

**`web-api/`** — REST API (internal Docker network only)
- Not exposed directly; Next.js proxies requests via `/api/proxy/[...path]`
- Routes: `auth`, `users`, `leaderboard`, `articles`, `tags`, `media`, `admin`, `xp`, `notifications`, `endorsements`, `activity`, `quests`, `comments`, `automod_api` (15 modules total)
- Auth: validates sessions via BetterAuth tables (reads from web's DB session)
- Rate limited via slowapi; CORS allows only `localhost:3000` and `web:3000`
- Calls `http://bot:8001` for Discord moderation actions
- Shares `/app/media` volume with the bot container

**`web/`** — Next.js 14 frontend
- TypeScript, Tailwind CSS, Radix UI, next-intl (fr/en i18n)
- All routes are under `src/app/[locale]/` — dynamic locale prefix drives i18n
- Auth via BetterAuth (Discord OAuth2); session cookie used across all requests
- API calls go through Next.js proxy routes at `/api/proxy/[...path]` → `web-api`
- Built with `output: 'standalone'` — runs as a Node.js server, not static

---

## Auth Flow

1. User clicks login → Discord OAuth2 redirect (handled by BetterAuth in `web/`)
2. BetterAuth stores the session in PostgreSQL (web's DB)
3. Subsequent requests: browser sends session cookie to Next.js
4. Next.js proxy forwards cookie to `web-api`
5. `web-api/middleware/auth_middleware.py` validates the session by reading BetterAuth tables directly from the DB

---

## Bot — Cog System

Cogs live in `bot/cogs/{fun,gamification,moderation,system,utilities}/`. Auto-discovered by `bot/utils/constants.py::cogs_names()` — every `.py` file in those directories is loaded. No manual registration needed.

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

Global `asyncpg` pool shared across the process. Manager singletons initialized at import time:

| Manager | Purpose |
|---|---|
| `voice_manager` | Voice time tracking, member sync |
| `warn_manager` | Moderation warnings |
| `message_stats_manager` | Per-channel message counts |
| `xp_manager` | XP, levels, leaderboard |
| `streak_manager` | Voice + message streaks |
| `quest_manager` | Weekly quests, progress, claim |
| `notification_manager` | In-app notifications |
| `command_stats_manager` | Per-user command usage counts |
| `bump_manager` | DISBOARD bump tracking |
| `invite_manager` | Invite tracking |
| `achievement_manager` | Achievement unlock & check |

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

Create a `.env` file at the repo root (used by Docker Compose and local runs). See `.env.example` for the full list.

| Variable | Required | Description |
|---|---|---|
| `DISCORD_TOKEN` | ✅ | Bot token |
| `GUILD_ID` | ✅ | Target guild ID |
| `BOT_CHANNEL_START` | ✅ | Startup message channel |
| `BOT_API_TOKEN` | ✅ | Shared secret between web-api and bot internal API |
| `PG_HOST` / `PG_PORT` / `PG_DB` / `PG_USER` / `PG_PASSWORD` | ✅ | PostgreSQL credentials |
| `DISCORD_CLIENT_ID` / `DISCORD_CLIENT_SECRET` | ✅ (web) | OAuth2 app credentials |
| `NEXT_PUBLIC_API_URL` | ✅ (web) | Public URL for client-side API calls |
| `NEXT_PUBLIC_APP_URL` | ✅ (web) | Public URL of the web app (used by BetterAuth) |
| `BETTER_AUTH_SECRET` | ✅ (web) | Secret key for BetterAuth session signing |
| `WEB_API_INTERNAL_URL` | ✅ (compose) | Internal URL of web-api (`http://web-api:8000`) |
| `BOT_API_URL` | ✅ (compose) | Internal URL of bot API (`http://bot:8001`) |
| `LOG_CHANNEL_ID` | ✅ | Default log channel |
| `VOICE_LOG_CHANNEL_ID` | | Voice-specific logs |
| `CONFESSION_CHANNEL_ID` | | Confession system |
| `ANIME_NEWS_CHANNEL_ID` | | Anime article feed |
| `ADMIN_ROLE_NAME` | | Role name for admin commands (default: `Administration`) |
| `AUTHORIZED_ROLES` | | Comma-separated moderation roles |
| `BLAGUES_API_TOKEN` | | Joke API |

---

## Bot — Cog Inventory

### `bot/cogs/gamification/`
| File | Commands |
|---|---|
| `xp.py` | `/level`, `/leaderboard-xp` |
| `streaks.py` | `/streak` |
| `weekly_quests.py` | `/quests`, `/quest-claim` |
| `stats.py` | `/stats` — stats complètes avec rangs |
| `classement.py` | `/classement` — leaderboard unifié 8 catégories (xp/vocal/messages/bumps/invitations/streaks/achievements/global) |
| `achievements.py` | Achievement check triggers |

### `bot/cogs/utilities/`
| File | Commands |
|---|---|
| `info_commands.py` | `/profile`, `/top-today`, `/compare` |
| `anime.py` | `/check_articles` |

### `bot/cogs/moderation/`
| File | Commands |
|---|---|
| `warn.py` | `/warn`, `/warns`, `/delwarn` |
| `kick.py` | `/kick` |
| `tempban.py` | `/tempban` |
| `tempmute.py` | `/tempmute` |
| `clear.py` | `/clear` |
| `audit.py` | `/audit` — profil d'audit admin (éphémère) |
| `automod.py` | Automod passif |
| `voice.py` | Tracking vocal passif |

### `bot/cogs/system/`
| File | Role |
|---|---|
| `achievements_notifier.py` | DM + rôle auto-créé/attribué au débloquage ; backfill one-shot au démarrage |
| `bump_tracker.py` | Détection bump DISBOARD |
| `invite_tracker.py` | Tracking invitations |
| `command_management.py` | `/enable-command`, `/disable-command`, `/commands-status` |
| `welcome.py` | Welcome messages for new members |
| `metrics_updater.py` | Prometheus metrics updates |
| `reaction_roles.py` | Embed réaction roles dans `REACTION_ROLE_CHANNEL_ID` ; crée les rôles manquants au démarrage |

### `bot/cogs/fun/`
| File | Commands |
|---|---|
| `blague.py` | `/blague` |
| `confess.py` | `/confess` |
| `game_lfg.py` | `/dbd`, `/lol`, `/warframe`, `/overwatch`, `/fortnite`, `/minecraft` — ping rôle jeu (cooldown 1h par forum, en mémoire) |

---

## Achievement Roles

When an achievement is unlocked (`AchievementsNotifier.notify`):
1. Role name = `{icon} {achievement_name}`
2. Role color = tier (Légendaire=gold, Épique=blue, Rare=orange, Commun=grey)
3. Role is created if it doesn't exist (requires bot **Gérer les rôles** permission, bot role above achievement roles)
4. Role is assigned to the member
5. DM sent with embed mentioning the role obtained

A one-shot `@tasks.loop(count=1)` task `backfill_roles` runs after `wait_until_ready()` to retroactively assign roles to all existing achievement holders in the DB.

---

## Database Migrations

Schema lives in `db/init.sql`. Migrations are in `db/migrations/` — run them manually against the running `db` container. There is no migration runner; apply SQL files in order by filename.

---

## Wiki Setup

`setup_wiki.py` (root) — one-shot script to create/populate the Discord forum wiki.
- Finds or creates a `#wiki` forum channel in `CATEGORY_ID = 776919447310565416`
- Creates 4 posts (threads), each with multiple styled embeds
- Run with: `python setup_wiki.py` (uses `.env` for token/guild)
- Safe to re-run — won't recreate the forum if `#wiki` already exists, but will add new threads

---

## Key Design Constraints

- **Async only** — no blocking I/O anywhere in bot or web-api code
- **No shared mutable state** between the bot's async event loop and the internal API thread (the internal API runs uvicorn in a daemon thread via `threading.Thread`)
- **Slash commands are guild-scoped** — synced to `GUILD_ID` only, not globally
- **Root-level v1 code** (`main.py`, `cogs/`, `utils/`) is legacy; don't extend it
- **web-api is Docker-internal** — never expose it directly; all public traffic goes through the Next.js proxy at `/api/proxy/[...path]`
