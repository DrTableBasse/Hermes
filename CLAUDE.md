# CLAUDE.md

This file provides **strict, actionable guidance** for Claude Code when working on the Hermes repository.

---

## Project Overview

**Hermes** is a modular Discord bot built with:

- discord.py (interactions / slash commands)
- PostgreSQL (persistent storage)
- asyncpg (async DB access)
- APScheduler (scheduled jobs)
- FastAPI (parallel HTTP API)

The bot and API run **concurrently** (bot = main thread, API = daemon thread).

---

## Quick Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Initialize PostgreSQL (once)
createdb saucisseland
psql -d saucisseland -f init-postgres.sql/init.sql

# Validate configuration
python config.py

# Run the bot
python main.py

# Linting
flake8 .

# Run tests
pytest
Core Architecture
1. Startup Flow (main.py)

Execution order is critical:

asyncio.run(main())
Start FastAPI server in a daemon thread
Connect Discord bot
on_ready event triggers:
Config validation
Database initialization (utils/database.py)
Table bootstrap (command_status)
Full guild member sync → user_voice_data
Cog loading (dynamic)
Slash command sync (guild-scoped)

⚠️ Important constraints

Anything DB-related must happen after pool initialization
Avoid heavy blocking logic in on_ready
2. Cog System (Auto-Discovery)

Located in:

cogs/
 ├── fun/
 ├── moderation/
 └── system/

Auto-loaded via utils/constants.py::cogs_names()

✅ To add a command:

Create a .py file in one of the folders
Implement:
async def setup(bot):
    await bot.add_cog(MyCog(bot))

🚫 Do NOT:

Manually register cogs
Hardcode imports in main.py
3. Database Layer (utils/database.py)

Uses a global asyncpg pool.

Managers (initialized at import time)
voice_manager → voice activity tracking
warn_manager → moderation infractions
Core Tables
Table	Purpose
user_voice_data	Voice time tracking
warn	Warnings & sanctions
user_message_stats	Message analytics
command_status	Command enable/disable

⚠️ Rules

Always use async queries (await)
Never create new connections manually (use pool)
Keep queries centralized in managers when possible
4. Command Enable/Disable System

Handled by CommandStatusManager (utils/command_manager.py)

Backed by DB
5-minute cache layer
Mandatory Pattern

Every command MUST check status:

is_enabled = await CommandStatusManager.get_command_status(
    command_name,
    guild_id=interaction.guild_id,
    use_cache=False
)

if not is_enabled:
    await interaction.response.send_message(
        f"❌ La commande `/{command_name}` est désactivée.",
        ephemeral=True
    )
    return

✅ Preferred:

@command_enabled()

🚫 Never skip this check

5. Logging System (utils/logging.py)

Structured logging via Discord embeds.

Channel priority
COMMAND_LOG_CHANNEL_ID
LOG_CHANNEL_ID (fallback)
Specialized channels
Admin → ADMIN_LOG_CHANNEL_ID
Voice → VOICE_LOG_CHANNEL_ID
Roles → ROLE_LOG_CHANNEL_ID
Sanctions → SANCTION_LOG_CHANNEL_ID
Confessions → CONFESSION_LOG_CHANNEL_ID
Usage
@log_command()

✅ Logs only on success
⚠️ Do not manually duplicate logs unless necessary

6. FastAPI Server
Runs in a separate daemon thread
Shares process with bot

⚠️ Constraints:

No blocking operations
Must not interfere with event loop
Avoid shared mutable state without protection
Development Conventions
General Rules
Use async everywhere (no blocking I/O)
Respect separation:
Cogs → logic layer
Managers → DB layer
Keep functions small and focused
Prefer composition over duplication
Command Design Rules

Every command should:

Check if enabled
Handle errors cleanly
Respond quickly (avoid timeout)
Use ephemeral responses when appropriate
Be logged via decorator
Error Handling
Never let exceptions reach Discord silently
Use structured logging for failures
Return user-friendly messages
Adding a New Feature
Identify category (fun, moderation, system)
Create cog file
Add DB logic (if needed) in a manager
Add command with:
status check
logging decorator
Test locally
Restart bot
Environment Variables

Create a .env file.

Required variables
Variable	Description
DISCORD_TOKEN	Bot token
GUILD_ID	Target guild
PG_HOST	PostgreSQL host
PG_PORT	PostgreSQL port
PG_DB	Database name
PG_USER	DB user
PG_PASSWORD	DB password
Feature-specific
Variable	Purpose
BLAGUES_API_TOKEN	Joke API
BOT_CHANNEL_START	Startup message
LOG_CHANNEL_ID	Default logs
VOICE_LOG_CHANNEL_ID	Voice logs
CONFESSION_CHANNEL_ID	Confession system
ANIME_NEWS_CHANNEL_ID	Anime feed
AUTHORIZED_ROLES	Moderation roles
Common Pitfalls (IMPORTANT)

❌ Forgetting await on DB calls
❌ Blocking the event loop
❌ Not checking command status
❌ Not using logging decorator
❌ Creating manual DB connections
❌ Modifying shared state between FastAPI & bot unsafely

Recommended Improvements (for future work)
Add migrations (Alembic)
Add typed models (pydantic)
Introduce service layer between cogs and DB
Improve test coverage (mock Discord + DB)

