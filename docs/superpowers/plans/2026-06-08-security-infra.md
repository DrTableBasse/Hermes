# Security & Infrastructure Hardening — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all security and infrastructure issues identified in the June 2026 audit: SQL injection pattern, missing rate limiting, permissive CORS, missing HTTP security headers, missing prometheus.yml, missing healthchecks, missing .dockerignore, and root-running containers.

**Architecture:** Code fixes are isolated to `web-api/` (Python/FastAPI). Infrastructure fixes touch `docker-compose.yml` and the three Dockerfiles. Prometheus config is a new file. No DB migrations required.

**Tech Stack:** FastAPI + SlowAPI (rate limiting), Next.js (security headers), Docker Compose, Prometheus

---

## File Map

| Action | File | What changes |
|--------|------|-------------|
| Modify | `web-api/routes/xp.py` | Remove f-string SQL, explicit whitelist |
| Modify | `web-api/routes/leaderboard.py` | Remove f-string SQL in `/xp` endpoint |
| Create | `web-api/limiter.py` | Shared SlowAPI limiter instance |
| Modify | `web-api/main.py` | Import limiter from new module |
| Modify | `web-api/routes/leaderboard.py` | Add `@limiter.limit()` + `Request` param |
| Modify | `web-api/routes/xp.py` | Add `@limiter.limit()` + `Request` param |
| Modify | `web-api/main.py` | Restrict CORS methods/headers |
| Modify | `web/next.config.mjs` | Add HTTP security headers |
| Create | `prometheus/prometheus.yml` | Scrape bot:8001/metrics |
| Modify | `docker-compose.yml` | Add healthchecks for bot, web-api, web |
| Modify | `bot/Dockerfile` | Add curl, non-root user |
| Modify | `web-api/Dockerfile` | Add curl, non-root user |
| Modify | `web/Dockerfile` | Non-root user (wget already on Alpine) |
| Create | `bot/.dockerignore` | Exclude .git, .env, __pycache__ |
| Create | `web-api/.dockerignore` | Exclude .git, .env, __pycache__ |
| Create | `web/.dockerignore` | Exclude .git, node_modules, .next |

---

## Task 1: Fix SQL injection pattern — xp.py

The `period` param is already gated via ternary, but the f-string into SQL is fragile. Replace with explicit conditional query selection.

**Files:**
- Modify: `web-api/routes/xp.py`

- [ ] **Step 1: Open the file and confirm current state**

Run: `cat web-api/routes/xp.py`
Expected: line 11 contains `f"...ORDER BY x.{col} DESC..."`

- [ ] **Step 2: Replace the f-string query with explicit branches**

Replace the entire `xp_leaderboard` function body:

```python
@router.get("/leaderboard")
async def xp_leaderboard(limit: int = 10, period: str = "all"):
    limit = max(1, min(limit, 100))
    if period == "weekly":
        rows = await db.fetch(
            "SELECT x.user_id, x.total_xp, x.weekly_xp, x.current_level, v.username, v.discord_avatar "
            "FROM user_xp x JOIN user_voice_data v ON x.user_id = v.user_id "
            "ORDER BY x.weekly_xp DESC LIMIT $1",
            limit,
        )
    else:
        rows = await db.fetch(
            "SELECT x.user_id, x.total_xp, x.weekly_xp, x.current_level, v.username, v.discord_avatar "
            "FROM user_xp x JOIN user_voice_data v ON x.user_id = v.user_id "
            "ORDER BY x.total_xp DESC LIMIT $1",
            limit,
        )
    return {"leaderboard": [dict(r) for r in rows]}
```

- [ ] **Step 3: Commit**

```bash
git add web-api/routes/xp.py
git commit -m "fix(security): remove f-string SQL interpolation in xp leaderboard"
```

---

## Task 2: Fix SQL injection pattern — leaderboard.py /xp endpoint

Same f-string issue in `leaderboard_xp()`.

**Files:**
- Modify: `web-api/routes/leaderboard.py` (the `leaderboard_xp` function only)

- [ ] **Step 1: Locate the function**

Run: `grep -n "f\"SELECT\|ORDER BY x\." web-api/routes/leaderboard.py`
Expected: lines around the `leaderboard_xp` function containing `f"...ORDER BY x.{col}..."`

- [ ] **Step 2: Replace with explicit branches**

Find this block in `leaderboard_xp`:
```python
    col    = "weekly_xp" if period == "weekly" else "total_xp"
    total = await db.fetchval("SELECT COUNT(*) FROM user_xp")
    rows  = await db.fetch(
        f"SELECT x.user_id, x.total_xp, x.weekly_xp, x.current_level, v.username, v.discord_avatar "
        f"FROM user_xp x JOIN user_voice_data v ON x.user_id = v.user_id "
        f"ORDER BY x.{col} DESC LIMIT $1 OFFSET $2",
        limit, offset,
    )
```

Replace with:
```python
    total = await db.fetchval("SELECT COUNT(*) FROM user_xp")
    if period == "weekly":
        rows = await db.fetch(
            "SELECT x.user_id, x.total_xp, x.weekly_xp, x.current_level, v.username, v.discord_avatar "
            "FROM user_xp x JOIN user_voice_data v ON x.user_id = v.user_id "
            "ORDER BY x.weekly_xp DESC LIMIT $1 OFFSET $2",
            limit, offset,
        )
    else:
        rows = await db.fetch(
            "SELECT x.user_id, x.total_xp, x.weekly_xp, x.current_level, v.username, v.discord_avatar "
            "FROM user_xp x JOIN user_voice_data v ON x.user_id = v.user_id "
            "ORDER BY x.total_xp DESC LIMIT $1 OFFSET $2",
            limit, offset,
        )
```

- [ ] **Step 3: Commit**

```bash
git add web-api/routes/leaderboard.py
git commit -m "fix(security): remove f-string SQL interpolation in leaderboard xp endpoint"
```

---

## Task 3: Rate limiting — create shared limiter module and apply to public routes

SlowAPI's limiter is initialized in `main.py` but never imported by routes. Create a shared module and apply limits to the two most-scraped public endpoints.

**Files:**
- Create: `web-api/limiter.py`
- Modify: `web-api/main.py`
- Modify: `web-api/routes/leaderboard.py`
- Modify: `web-api/routes/xp.py`

- [ ] **Step 1: Create `web-api/limiter.py`**

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
```

- [ ] **Step 2: Update `web-api/main.py` to import from the new module**

Find:
```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.middleware import SlowAPIMiddleware
from slowapi.errors import RateLimitExceeded
```

Replace with:
```python
from slowapi import _rate_limit_exceeded_handler
from slowapi.middleware import SlowAPIMiddleware
from slowapi.errors import RateLimitExceeded
from limiter import limiter
```

Find:
```python
limiter = Limiter(key_func=get_remote_address)
```

Delete that line (the limiter is now imported from `limiter.py`).

- [ ] **Step 3: Apply rate limit to leaderboard routes**

At the top of `web-api/routes/leaderboard.py`, add these imports:

```python
from fastapi import Request
from limiter import limiter
```

Then add `@limiter.limit("60/minute")` and a `request: Request` first parameter to each public GET handler. Example for `leaderboard_voice`:

```python
@router.get("/voice")
@limiter.limit("60/minute")
async def leaderboard_voice(request: Request, page: int = 1, limit: int = 10, search: str | None = None):
```

Apply the same pattern to: `leaderboard_messages`, `leaderboard_achievements`, `leaderboard_xp`, `leaderboard_global`, `leaderboard_bumps`, `leaderboard_invites`, `leaderboard_levels`, `leaderboard_streaks`.

The `/me` endpoint is authenticated — apply a tighter limit:
```python
@router.get("/me")
@limiter.limit("30/minute")
async def my_ranks(request: Request, user: dict = Depends(get_current_user)):
```

- [ ] **Step 4: Apply rate limit to xp routes**

At the top of `web-api/routes/xp.py`, add:
```python
from fastapi import Request
from limiter import limiter
```

Update both handlers:
```python
@router.get("/leaderboard")
@limiter.limit("60/minute")
async def xp_leaderboard(request: Request, limit: int = 10, period: str = "all"):

@router.get("/{user_id}")
@limiter.limit("60/minute")
async def get_user_xp(request: Request, user_id: int):
```

- [ ] **Step 5: Verify the server starts without errors**

```bash
cd web-api && pip install -r requirements.txt -q && python -c "import main; print('OK')"
```

Expected: `OK` (no import errors)

- [ ] **Step 6: Commit**

```bash
git add web-api/limiter.py web-api/main.py web-api/routes/leaderboard.py web-api/routes/xp.py
git commit -m "feat(security): apply SlowAPI rate limiting to public leaderboard and xp routes"
```

---

## Task 4: Harden CORS configuration

`allow_methods=["*"]` and `allow_headers=["*"]` are too permissive.

**Files:**
- Modify: `web-api/main.py`

- [ ] **Step 1: Replace the CORS middleware call**

Find:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://web:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Replace with:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://web:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Cookie"],
)
```

- [ ] **Step 2: Commit**

```bash
git add web-api/main.py
git commit -m "fix(security): restrict CORS methods and headers"
```

---

## Task 5: HTTP security headers in Next.js

**Files:**
- Modify: `web/next.config.mjs`

- [ ] **Step 1: Add headers() to the Next.js config**

Find:
```js
const nextConfig = {
  output: 'standalone',
  images: {
    remotePatterns: [
      { protocol: 'https', hostname: 'cdn.discordapp.com' },
      { protocol: 'http',  hostname: 'localhost' },
    ],
  },
}
```

Replace with:
```js
const securityHeaders = [
  { key: 'X-Frame-Options',        value: 'DENY' },
  { key: 'X-Content-Type-Options', value: 'nosniff' },
  { key: 'Referrer-Policy',        value: 'strict-origin-when-cross-origin' },
  { key: 'Permissions-Policy',     value: 'camera=(), microphone=(), geolocation=()' },
  {
    key: 'Content-Security-Policy',
    value: [
      "default-src 'self'",
      "script-src 'self' 'unsafe-inline'",
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data: https://cdn.discordapp.com",
      "connect-src 'self'",
      "font-src 'self'",
      "frame-ancestors 'none'",
    ].join('; '),
  },
]

const nextConfig = {
  output: 'standalone',
  images: {
    remotePatterns: [
      { protocol: 'https', hostname: 'cdn.discordapp.com' },
      { protocol: 'http',  hostname: 'localhost' },
    ],
  },
  async headers() {
    return [{ source: '/(.*)', headers: securityHeaders }]
  },
}
```

- [ ] **Step 2: Verify the build parses without error**

```bash
cd web && node -e "import('./next.config.mjs').then(m => console.log('OK'))"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add web/next.config.mjs
git commit -m "feat(security): add HTTP security headers to Next.js config"
```

---

## Task 6: Create prometheus/prometheus.yml

The bot exposes `/metrics` on port 8001. Prometheus is configured to mount this file but it doesn't exist.

**Files:**
- Create: `prometheus/prometheus.yml`

- [ ] **Step 1: Confirm the directory exists**

```bash
ls prometheus/
```

Expected: directory exists (it's referenced in docker-compose.yml volumes)

- [ ] **Step 2: Create the file**

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'hermes-bot'
    static_configs:
      - targets: ['bot:8001']
    metrics_path: '/metrics'
```

Save to `prometheus/prometheus.yml`.

- [ ] **Step 3: Commit**

```bash
git add prometheus/prometheus.yml
git commit -m "feat(infra): add prometheus scrape config for hermes-bot metrics"
```

---

## Task 7: Add healthchecks and curl to Dockerfiles

Bot and web-api have no healthcheck. Docker Compose depends_on `service_started` for web-api means web could start before web-api is ready.

**Files:**
- Modify: `bot/Dockerfile`
- Modify: `web-api/Dockerfile`
- Modify: `docker-compose.yml`

- [ ] **Step 1: Add curl to bot/Dockerfile**

Find:
```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*
```

Replace with:
```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*
```

- [ ] **Step 2: Add curl to web-api/Dockerfile**

Same change in `web-api/Dockerfile`:
```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*
```

- [ ] **Step 3: Add healthchecks in docker-compose.yml**

Under the `bot:` service, add after `networks:`:
```yaml
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8001/health"]
      interval: 15s
      timeout: 5s
      retries: 5
      start_period: 10s
```

Under the `web-api:` service, add after `networks:`:
```yaml
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 15s
      timeout: 5s
      retries: 5
      start_period: 10s
```

Under the `web:` service, add after `networks:` (Alpine has wget):
```yaml
    healthcheck:
      test: ["CMD-SHELL", "wget -qO- http://localhost:3000/ > /dev/null || exit 1"]
      interval: 15s
      timeout: 5s
      retries: 5
      start_period: 30s
```

- [ ] **Step 4: Tighten the web depends_on for web-api**

Find in `web:` service:
```yaml
      web-api:
        condition: service_started
```

Replace with:
```yaml
      web-api:
        condition: service_healthy
```

- [ ] **Step 5: Commit**

```bash
git add bot/Dockerfile web-api/Dockerfile docker-compose.yml
git commit -m "feat(infra): add healthchecks for bot, web-api, web containers"
```

---

## Task 8: Add .dockerignore files

Without `.dockerignore`, `COPY . .` sends `.git/`, `.env`, `__pycache__/`, and SQL backups into the build context.

**Files:**
- Create: `bot/.dockerignore`
- Create: `web-api/.dockerignore`
- Create: `web/.dockerignore`

- [ ] **Step 1: Create bot/.dockerignore**

```
.git
.env
*.env
__pycache__
*.pyc
*.pyo
*.md
tests/
*.sql
.pytest_cache
```

- [ ] **Step 2: Create web-api/.dockerignore**

```
.git
.env
*.env
__pycache__
*.pyc
*.pyo
*.md
tests/
*.sql
.pytest_cache
```

- [ ] **Step 3: Create web/.dockerignore**

```
.git
.env*
node_modules
.next
*.md
.pytest_cache
```

- [ ] **Step 4: Commit**

```bash
git add bot/.dockerignore web-api/.dockerignore web/.dockerignore
git commit -m "feat(infra): add .dockerignore to all services to reduce build context"
```

---

## Task 9: Run containers as non-root users

All three Dockerfiles run as root. Add a non-privileged user to each.

**Files:**
- Modify: `bot/Dockerfile`
- Modify: `web-api/Dockerfile`
- Modify: `web/Dockerfile`

- [ ] **Step 1: Update bot/Dockerfile**

Find the final lines:
```dockerfile
COPY . .

CMD ["python", "main.py"]
```

Replace with:
```dockerfile
COPY . .

RUN adduser --disabled-password --gecos "" appuser \
    && chown -R appuser:appuser /app
USER appuser

CMD ["python", "main.py"]
```

- [ ] **Step 2: Update web-api/Dockerfile**

Find the final lines:
```dockerfile
COPY . .

RUN mkdir -p /app/media

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Replace with:
```dockerfile
COPY . .

RUN mkdir -p /app/media \
    && adduser --disabled-password --gecos "" appuser \
    && chown -R appuser:appuser /app
USER appuser

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 3: Update web/Dockerfile (runner stage)**

In `web/Dockerfile`, the final stage starts with `FROM node:20-alpine AS runner`. Find the final lines of that stage:

```dockerfile
EXPOSE 3000
CMD ["node", "server.js"]
```

Replace with:
```dockerfile
RUN addgroup -S appgroup && adduser -S appuser -G appgroup \
    && chown -R appuser:appgroup /app
USER appuser

EXPOSE 3000
CMD ["node", "server.js"]
```

- [ ] **Step 4: Verify docker builds succeed**

```bash
docker build -t hermes-bot-test ./bot
docker build -t hermes-webapi-test ./web-api
docker build -t hermes-web-test ./web
```

Expected: all three build without errors. Run `docker image rm hermes-bot-test hermes-webapi-test hermes-web-test` to clean up.

- [ ] **Step 5: Commit**

```bash
git add bot/Dockerfile web-api/Dockerfile web/Dockerfile
git commit -m "feat(infra): run all containers as non-root appuser"
```

---

## Task 10: Smoke test — full stack

- [ ] **Step 1: Start the stack**

```bash
docker compose up --build -d
```

- [ ] **Step 2: Wait for all containers to be healthy**

```bash
docker compose ps
```

Expected: all services show `healthy` (db, bot, web-api, web) or `running` for prometheus/grafana.

- [ ] **Step 3: Verify rate limiting header is present**

```bash
curl -I http://localhost:3000/api/proxy/leaderboard/voice?page=1
```

Expected: response contains `X-RateLimit-Limit` header (SlowAPI injects this).

- [ ] **Step 4: Verify security headers are present**

```bash
curl -I http://localhost:3000/
```

Expected: response contains `x-frame-options: DENY` and `x-content-type-options: nosniff`.

- [ ] **Step 5: Verify prometheus is scraping**

```bash
curl http://localhost:9090/api/v1/targets 2>/dev/null | python -m json.tool | grep "hermes-bot"
```

Expected: `"hermes-bot"` appears in output.

- [ ] **Step 6: Stop the stack**

```bash
docker compose down
```
