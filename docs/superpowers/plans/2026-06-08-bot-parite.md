# Bot Parité — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add four missing parity features: Discord `/achievements` command, web activity heatmap on profile, web `/compare` page, and web `/top-weekly` page.

**Architecture:** Bot-side adds a single cog (`achievements.py`) following the exact pattern of `stats.py`. Web-side adds: a public stats endpoint to `web-api` (no auth required, for compare), four new server-api.ts functions, a new `ActivityHeatmap` React component, two new pages (`/compare`, `/top-weekly`), and a heatmap section on the profile page. The compare page works with zero auth — it uses a new `GET /users/{id}/public` endpoint that returns community-visible stats only.

**Tech Stack:** discord.py app_commands, Next.js 15 App Router (Server Components), FastAPI + asyncpg, TypeScript, Tailwind CSS

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `bot/cogs/gamification/achievements.py` | `/achievements` slash command |
| Modify | `web-api/routes/users.py` | Add `GET /{user_id}/public` (no auth) |
| Modify | `web/src/lib/server-api.ts` | Add `serverGetUserActivity`, `serverGetUserPublicStats`, `serverSearchUserByUsername`, `serverLeaderboardXpWeekly` + `PublicUserStats` type |
| Create | `web/src/components/ActivityHeatmap.tsx` | GitHub-style CSS heatmap component |
| Modify | `web/src/app/[locale]/profile/page.tsx` | Add activity data fetch + heatmap section |
| Create | `web/src/app/[locale]/compare/page.tsx` | Side-by-side user comparison (Server Component) |
| Create | `web/src/app/[locale]/top-weekly/page.tsx` | Weekly XP + all-time messages top 10 |

---

## Task 1: Bot `/achievements` command

**Files:**
- Create: `bot/cogs/gamification/achievements.py`

Tier thresholds come from `achievements_notifier.py`'s `_tier()` function — **Commun** < 25 pts, **Rare** 25–49, **Épique** 50–99, **Légendaire** ≥ 100. No `rarity` column in DB — always computed from `points`.

- [ ] **Step 1: Create `bot/cogs/gamification/achievements.py`**

```python
"""Affiche les achievements débloqués d'un membre."""
import logging
import discord
from discord import app_commands
from discord.ext import commands

from utils.database import db_manager
from utils.command_manager import command_enabled
from utils.embed_style import hermes_embed, Colors

logger = logging.getLogger(__name__)


def _tier(points: int) -> tuple[int, str]:
    if points >= 100:
        return Colors.GOLD,   "Légendaire"
    if points >= 50:
        return Colors.BLUE,   "Épique"
    if points >= 25:
        return Colors.ORANGE, "Rare"
    return Colors.GREY,       "Commun"


_TIER_EMOJI = {
    "Légendaire": "⭐",
    "Épique":     "💎",
    "Rare":       "🔶",
    "Commun":     "⚪",
}


class AchievementsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="achievements",
        description="Voir les achievements débloqués d'un membre",
    )
    @command_enabled(guild_specific=True)
    async def achievements_cmd(
        self,
        interaction: discord.Interaction,
        user: discord.Member = None,
    ):
        await interaction.response.defer()
        target = user or interaction.user

        rows = await db_manager.fetch("""
            SELECT a.name, a.description, a.icon, a.points, ua.unlocked_at
            FROM user_achievements ua
            JOIN achievements a ON a.id = ua.achievement_id
            WHERE ua.user_id = $1
            ORDER BY a.points DESC, ua.unlocked_at ASC
        """, target.id)

        total_pts = sum(r["points"] for r in rows)
        count = len(rows)

        embed = hermes_embed(
            title=f"🏆  Achievements — {target.display_name}",
            description=(
                f"**{count}** achievement{'s' if count != 1 else ''} débloqué{'s' if count != 1 else ''} "
                f"· **{total_pts} pts**"
            ),
            color=Colors.GOLD,
            thumbnail_url=target.display_avatar.url,
        )

        if not rows:
            embed.add_field(
                name="Aucun achievement",
                value="Participe au serveur pour débloquer tes premiers achievements !",
                inline=False,
            )
        else:
            tier_groups: dict[str, list[str]] = {
                "Légendaire": [], "Épique": [], "Rare": [], "Commun": [],
            }
            for r in rows:
                _, label = _tier(r["points"])
                icon = r["icon"] or "🏆"
                date_str = r["unlocked_at"].strftime("%d/%m/%Y") if r["unlocked_at"] else "?"
                line = f"{icon} **{r['name']}** · {r['points']} pts · *{date_str}*"
                tier_groups[label].append(line)

            for label in ("Légendaire", "Épique", "Rare", "Commun"):
                entries = tier_groups[label]
                if not entries:
                    continue
                display = entries[:15]
                value = "\n".join(display)
                if len(entries) > 15:
                    value += f"\n*…et {len(entries) - 15} de plus*"
                embed.add_field(
                    name=f"{_TIER_EMOJI[label]} {label}  ({len(entries)})",
                    value=value,
                    inline=False,
                )

        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(AchievementsCog(bot))
```

- [ ] **Step 2: Verify the cog is auto-discovered**

The bot loads all `.py` files from `bot/cogs/gamification/` automatically (via `cogs_names()` in `bot/utils/constants.py`). No registration needed. Confirm by checking the directory:

```bash
ls bot/cogs/gamification/
```

Expected: `achievements.py` appears alongside `xp.py`, `stats.py`, etc.

- [ ] **Step 3: Commit**

```bash
git add bot/cogs/gamification/achievements.py
git commit -m "feat(bot): add /achievements command grouped by tier"
```

---

## Task 2: Web-api — public user stats endpoint

**Files:**
- Modify: `web-api/routes/users.py`

This endpoint is unauthenticated — it returns only public community stats (no warns details, no private info). Required by the `/compare` page which must work without login.

- [ ] **Step 1: Read `web-api/routes/users.py` to find the end of the file**

```bash
tail -30 web-api/routes/users.py
```

Expected: see the last endpoint definition and any `# EOF` or blank lines at the end.

- [ ] **Step 2: Add the public stats endpoint**

Append this function to `web-api/routes/users.py` (after all existing endpoints, before EOF):

```python
from fastapi import Request as _Request  # already imported if not aliased elsewhere


@router.get("/{user_id}/public")
@limiter.limit("60/minute")
async def get_user_public_stats(request: Request, user_id: int):
    """Public stats — no auth required. Returns community-visible data only."""
    user = await db.fetchrow(
        "SELECT user_id, username, nickname, discord_avatar FROM user_voice_data WHERE user_id = $1",
        user_id,
    )
    if not user:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="User not found")

    total_messages, voice_row, xp_row, ach_count, streak_row, bump_count = await asyncio.gather(
        db.fetchval(
            "SELECT COALESCE(SUM(message_count), 0) FROM user_message_stats WHERE user_id = $1",
            user_id,
        ),
        db.fetchrow("SELECT total_time FROM user_voice_data WHERE user_id = $1", user_id),
        db.fetchrow("SELECT total_xp, current_level FROM user_xp WHERE user_id = $1", user_id),
        db.fetchval("SELECT COUNT(*) FROM user_achievements WHERE user_id = $1", user_id),
        db.fetchrow(
            "SELECT current_streak, max_streak FROM user_streaks WHERE user_id = $1", user_id
        ),
        db.fetchval(
            "SELECT COALESCE(bump_count, 0) FROM user_bump_stats WHERE user_id = $1", user_id
        ),
    )

    s = voice_row["total_time"] if voice_row else 0
    h, rem = divmod(s, 3600)
    m, _ = divmod(rem, 60)

    return {
        "user_id":        str(user_id),
        "username":       user["username"],
        "nickname":       user["nickname"],
        "discord_avatar": user["discord_avatar"],
        "stats": {
            "total_messages":    int(total_messages or 0),
            "voice_seconds":     s,
            "voice_formatted":   f"{h}h {m}m",
            "total_xp":          xp_row["total_xp"] if xp_row else 0,
            "current_level":     xp_row["current_level"] if xp_row else 0,
            "achievement_count": int(ach_count or 0),
            "current_streak":    streak_row["current_streak"] if streak_row else 0,
            "bump_count":        int(bump_count or 0),
        },
    }
```

**Important:** `asyncio` is already imported at the top of `users.py` (used in `_check_achievements`). If it's not, add `import asyncio` at the top. Also `Request` must already be imported from `fastapi` since other endpoints use rate limiting.

Check the top of the file: if `from fastapi import APIRouter, Depends, HTTPException` is the current import line, add `Request` to it:
```python
from fastapi import APIRouter, Depends, HTTPException, Request
```

And add the limiter import if missing:
```python
from limiter import limiter
```

- [ ] **Step 3: Commit**

```bash
git add web-api/routes/users.py
git commit -m "feat(api): add GET /users/{id}/public — unauthenticated public stats"
```

---

## Task 3: server-api.ts — add 4 functions + 1 type

**Files:**
- Modify: `web/src/lib/server-api.ts`

- [ ] **Step 1: Update the import line at the top of `web/src/lib/server-api.ts`**

Find:
```ts
import type { Article, ArticleList, Tag, VoiceEntry, LeaderboardEntry } from './api'
```

Replace with:
```ts
import type { Article, ArticleList, Tag, VoiceEntry, LeaderboardEntry, ActivityDay, XPEntry } from './api'
```

- [ ] **Step 2: Add the `PublicUserStats` interface and four new functions**

Append to the end of `web/src/lib/server-api.ts`:

```ts
// ── Public user stats (no auth — for compare page) ────────────────────────────

export interface PublicUserStats {
  user_id:        string
  username:       string
  nickname:       string | null
  discord_avatar: string | null
  stats: {
    total_messages:    number
    voice_seconds:     number
    voice_formatted:   string
    total_xp:          number
    current_level:     number
    achievement_count: number
    current_streak:    number
    bump_count:        number
  }
}

export async function serverGetUserPublicStats(userId: string): Promise<PublicUserStats> {
  return get<PublicUserStats>(`/users/${userId}/public`)
}

export async function serverSearchUserByUsername(
  query: string,
): Promise<{ user_id: string; username: string; discord_avatar: string | null } | null> {
  try {
    const data = await get<LbPage<LeaderboardEntry>>(
      `/leaderboard/messages?search=${encodeURIComponent(query)}&limit=1`,
    )
    const first = data.leaderboard[0]
    if (!first) return null
    return { user_id: String(first.user_id), username: first.username, discord_avatar: first.discord_avatar }
  } catch {
    return null
  }
}

// ── Activity heatmap ──────────────────────────────────────────────────────────

export async function serverGetUserActivity(userId: string): Promise<{ heatmap: ActivityDay[] }> {
  try {
    return await get<{ heatmap: ActivityDay[] }>(`/activity/${userId}/heatmap?days=365`)
  } catch {
    return { heatmap: [] }
  }
}

// ── Weekly XP leaderboard ─────────────────────────────────────────────────────

export async function serverLeaderboardXpWeekly(limit = 10): Promise<XPEntry[]> {
  try {
    const data = await get<{ leaderboard: XPEntry[] }>(
      `/xp/leaderboard?period=weekly&limit=${limit}`,
    )
    return data.leaderboard
  } catch {
    return []
  }
}
```

- [ ] **Step 3: TypeScript check**

```bash
cd web && npx tsc --noEmit 2>&1 | head -20
```

Expected: no errors

- [ ] **Step 4: Commit**

```bash
git add web/src/lib/server-api.ts
git commit -m "feat(web): add serverGetUserActivity, serverGetUserPublicStats, serverSearchUserByUsername, serverLeaderboardXpWeekly"
```

---

## Task 4: ActivityHeatmap component

**Files:**
- Create: `web/src/components/ActivityHeatmap.tsx`

GitHub-style heatmap: 52 columns (weeks) × 7 rows (days). No external library. Server Component (no `'use client'`).

- [ ] **Step 1: Create `web/src/components/ActivityHeatmap.tsx`**

```tsx
import type { ActivityDay } from '@/lib/api'

interface Props {
  data: ActivityDay[]
}

function intensity(count: number): 0 | 1 | 2 | 3 | 4 {
  if (count === 0)  return 0
  if (count <= 2)   return 1
  if (count <= 5)   return 2
  if (count <= 10)  return 3
  return 4
}

const CELL = [
  'bg-white/5',
  'bg-accent/20',
  'bg-accent/40',
  'bg-accent/65',
  'bg-accent',
]

export default function ActivityHeatmap({ data }: Props) {
  const countMap = new Map(data.map(d => [d.date, d.count]))

  // Build a 53-week grid, starting on Sunday, ending today
  const today = new Date()
  const start = new Date(today)
  start.setDate(today.getDate() - 364)
  start.setDate(start.getDate() - start.getDay()) // rewind to Sunday

  const weeks: { date: string; count: number }[][] = []
  const cur = new Date(start)
  let week: { date: string; count: number }[] = []

  while (cur <= today) {
    const iso = cur.toISOString().slice(0, 10)
    week.push({ date: iso, count: countMap.get(iso) ?? 0 })
    if (week.length === 7) {
      weeks.push(week)
      week = []
    }
    cur.setDate(cur.getDate() + 1)
  }
  if (week.length) weeks.push(week)

  const totalMessages = data.reduce((s, d) => s + d.count, 0)

  return (
    <div>
      <div className="overflow-x-auto pb-1">
        <div className="flex gap-[3px]" style={{ width: 'fit-content' }}>
          {weeks.map((wk, wi) => (
            <div key={wi} className="flex flex-col gap-[3px]">
              {wk.map((day, di) => (
                <div
                  key={di}
                  title={`${day.date} · ${day.count} message${day.count !== 1 ? 's' : ''}`}
                  className={`w-[10px] h-[10px] rounded-[2px] ${CELL[intensity(day.count)]}`}
                />
              ))}
            </div>
          ))}
        </div>
      </div>
      <p className="text-xs text-muted-foreground mt-2">
        {totalMessages.toLocaleString()} message{totalMessages !== 1 ? 's' : ''} sur les 12 derniers mois
      </p>
    </div>
  )
}
```

- [ ] **Step 2: TypeScript check**

```bash
cd web && npx tsc --noEmit 2>&1 | head -20
```

Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add web/src/components/ActivityHeatmap.tsx
git commit -m "feat(web): add ActivityHeatmap component (GitHub-style, no library)"
```

---

## Task 5: Profile page — add heatmap section

**Files:**
- Modify: `web/src/app/[locale]/profile/page.tsx`

- [ ] **Step 1: Read the full profile page**

```bash
cat web/src/app/\[locale\]/profile/page.tsx
```

This will show the full structure. Identify:
- Where `serverGetUserStats` is called (around line 24)
- Where the Stats section `<section className="mb-12">` ends (look for the matching `</section>`)
- The achievements section that follows (look for `achievements` in the code)

- [ ] **Step 2: Add ActivityHeatmap import**

Find:
```ts
import { serverGetUserStats } from '@/lib/server-api'
```

Replace with:
```ts
import { serverGetUserStats, serverGetUserActivity } from '@/lib/server-api'
import ActivityHeatmap from '@/components/ActivityHeatmap'
```

- [ ] **Step 3: Add activity data fetch alongside the existing stats fetch**

Find:
```ts
  let data = null
  try { data = await serverGetUserStats(u.discordId, token) } catch {}
```

Replace with:
```ts
  let data = null
  let activityData = null
  try { data = await serverGetUserStats(u.discordId, token) } catch {}
  try { activityData = await serverGetUserActivity(u.discordId) } catch {}
```

- [ ] **Step 4: Add heatmap section after the stats section**

Find the closing tag of the stats section. It will look like:
```tsx
      </section>

      {/* (next section — achievements or similar) */}
```

Right after the `</section>` of the stats section (before the achievements section), insert:

```tsx
      {/* Activité */}
      <section className="mb-12">
        <h2 className="text-xl font-bold mb-5">📅 Activité</h2>
        <div className="glass-card p-5">
          <p className="text-sm text-muted-foreground mb-4">Messages envoyés — 12 derniers mois</p>
          <ActivityHeatmap data={activityData?.heatmap ?? []} />
        </div>
      </section>
```

- [ ] **Step 5: TypeScript check**

```bash
cd web && npx tsc --noEmit 2>&1 | head -20
```

Expected: no errors

- [ ] **Step 6: Commit**

```bash
git add web/src/app/\[locale\]/profile/page.tsx
git commit -m "feat(web): add activity heatmap to profile page"
```

---

## Task 6: Web `/compare` page

**Files:**
- Create: `web/src/app/[locale]/compare/page.tsx`

Server Component. Accepts `?u1=username1&u2=username2` via GET form submission. Searches users by username via the leaderboard messages endpoint, then fetches their public stats. No authentication required.

- [ ] **Step 1: Create `web/src/app/[locale]/compare/page.tsx`**

```tsx
import type { Metadata } from 'next'
import Image from 'next/image'
import {
  serverSearchUserByUsername,
  serverGetUserPublicStats,
  type PublicUserStats,
} from '@/lib/server-api'

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>
}): Promise<Metadata> {
  const { locale } = await params
  return {
    title: 'Comparer',
    description:
      locale === 'fr'
        ? 'Comparez les statistiques de deux membres SaucisseLand côte à côte.'
        : 'Compare statistics of two SaucisseLand members side by side.',
  }
}

interface StatRowProps {
  label:   string
  v1:      string | number
  v2:      string | number
  numVal1: number
  numVal2: number
}

function StatRow({ label, v1, v2, numVal1, numVal2 }: StatRowProps) {
  const win1 = numVal1 > numVal2
  const win2 = numVal2 > numVal1
  return (
    <tr className="border-b border-border/20">
      <td className={`py-3 px-4 text-right font-bold tabular-nums ${win1 ? 'text-accent' : ''}`}>
        {win1 && <span className="mr-1 text-accent">▶</span>}{v1}
      </td>
      <td className="py-3 px-4 text-center text-xs text-muted-foreground uppercase tracking-wide">
        {label}
      </td>
      <td className={`py-3 px-4 text-left font-bold tabular-nums ${win2 ? 'text-accent' : ''}`}>
        {v2}{win2 && <span className="ml-1 text-accent">◀</span>}
      </td>
    </tr>
  )
}

function UserHeader({ user }: { user: PublicUserStats }) {
  return (
    <div className="flex flex-col items-center gap-2 p-4">
      {user.discord_avatar ? (
        <Image
          src={user.discord_avatar}
          alt={user.username}
          width={56}
          height={56}
          className="rounded-full ring-2 ring-border/60"
        />
      ) : (
        <div className="w-14 h-14 rounded-full bg-accent/20 flex items-center justify-center text-xl font-bold">
          {user.username[0]?.toUpperCase()}
        </div>
      )}
      <div className="font-bold text-sm">{user.nickname ?? user.username}</div>
      {user.nickname && (
        <div className="text-xs text-muted-foreground">@{user.username}</div>
      )}
    </div>
  )
}

export default async function ComparePage({
  params,
  searchParams,
}: {
  params:       Promise<{ locale: string }>
  searchParams: Promise<{ u1?: string; u2?: string }>
}) {
  const [{ locale }, { u1, u2 }] = await Promise.all([params, searchParams])
  const isFr = locale === 'fr'

  // Resolve usernames → user IDs → public stats
  let stats1: PublicUserStats | null = null
  let stats2: PublicUserStats | null = null
  let err1: string | null = null
  let err2: string | null = null

  if (u1) {
    const found = await serverSearchUserByUsername(u1)
    if (found) {
      try { stats1 = await serverGetUserPublicStats(found.user_id) }
      catch { err1 = isFr ? 'Erreur lors du chargement.' : 'Failed to load.' }
    } else {
      err1 = isFr ? `Utilisateur "${u1}" introuvable.` : `User "${u1}" not found.`
    }
  }

  if (u2) {
    const found = await serverSearchUserByUsername(u2)
    if (found) {
      try { stats2 = await serverGetUserPublicStats(found.user_id) }
      catch { err2 = isFr ? 'Erreur lors du chargement.' : 'Failed to load.' }
    } else {
      err2 = isFr ? `Utilisateur "${u2}" introuvable.` : `User "${u2}" not found.`
    }
  }

  return (
    <div className="container mx-auto px-4 py-12 max-w-3xl">
      <h1 className="text-3xl font-extrabold tracking-tight mb-2">
        ⚔️ {isFr ? 'Comparer' : 'Compare'}
      </h1>
      <p className="text-muted-foreground mb-8">
        {isFr
          ? 'Entrez deux pseudos Discord pour comparer leurs statistiques.'
          : 'Enter two Discord usernames to compare their stats.'}
      </p>

      {/* Search form */}
      <form method="GET" className="flex flex-col sm:flex-row gap-3 mb-10">
        <input
          name="u1"
          defaultValue={u1 ?? ''}
          placeholder={isFr ? 'Joueur 1…' : 'Player 1…'}
          className="flex-1 px-4 py-2 rounded-lg bg-card border border-border/50 text-sm focus:outline-none focus:ring-2 focus:ring-accent/50"
        />
        <input
          name="u2"
          defaultValue={u2 ?? ''}
          placeholder={isFr ? 'Joueur 2…' : 'Player 2…'}
          className="flex-1 px-4 py-2 rounded-lg bg-card border border-border/50 text-sm focus:outline-none focus:ring-2 focus:ring-accent/50"
        />
        <button
          type="submit"
          className="px-6 py-2 rounded-lg bg-accent text-accent-foreground font-semibold text-sm hover:bg-accent/80 transition-colors"
        >
          {isFr ? 'Comparer' : 'Compare'}
        </button>
      </form>

      {/* Error messages */}
      {err1 && <p className="text-red-400 text-sm mb-2">{err1}</p>}
      {err2 && <p className="text-red-400 text-sm mb-4">{err2}</p>}

      {/* Comparison table */}
      {stats1 && stats2 && (
        <div className="glass-card overflow-hidden">
          {/* User headers */}
          <div className="grid grid-cols-3 border-b border-border/30">
            <UserHeader user={stats1} />
            <div className="flex items-center justify-center text-2xl font-black text-muted-foreground">
              VS
            </div>
            <UserHeader user={stats2} />
          </div>

          {/* Stats rows */}
          <table className="w-full">
            <tbody>
              <StatRow
                label={isFr ? '💬 Messages' : '💬 Messages'}
                v1={stats1.stats.total_messages.toLocaleString()}
                v2={stats2.stats.total_messages.toLocaleString()}
                numVal1={stats1.stats.total_messages}
                numVal2={stats2.stats.total_messages}
              />
              <StatRow
                label={isFr ? '🎤 Vocal' : '🎤 Voice'}
                v1={stats1.stats.voice_formatted}
                v2={stats2.stats.voice_formatted}
                numVal1={stats1.stats.voice_seconds}
                numVal2={stats2.stats.voice_seconds}
              />
              <StatRow
                label="⚡ XP"
                v1={stats1.stats.total_xp.toLocaleString()}
                v2={stats2.stats.total_xp.toLocaleString()}
                numVal1={stats1.stats.total_xp}
                numVal2={stats2.stats.total_xp}
              />
              <StatRow
                label={isFr ? '📊 Niveau' : '📊 Level'}
                v1={stats1.stats.current_level}
                v2={stats2.stats.current_level}
                numVal1={stats1.stats.current_level}
                numVal2={stats2.stats.current_level}
              />
              <StatRow
                label={isFr ? '🏆 Achievements' : '🏆 Achievements'}
                v1={stats1.stats.achievement_count}
                v2={stats2.stats.achievement_count}
                numVal1={stats1.stats.achievement_count}
                numVal2={stats2.stats.achievement_count}
              />
              <StatRow
                label={isFr ? '🔥 Streak' : '🔥 Streak'}
                v1={`${stats1.stats.current_streak}j`}
                v2={`${stats2.stats.current_streak}j`}
                numVal1={stats1.stats.current_streak}
                numVal2={stats2.stats.current_streak}
              />
              <StatRow
                label={isFr ? '📣 Bumps' : '📣 Bumps'}
                v1={stats1.stats.bump_count.toLocaleString()}
                v2={stats2.stats.bump_count.toLocaleString()}
                numVal1={stats1.stats.bump_count}
                numVal2={stats2.stats.bump_count}
              />
            </tbody>
          </table>
        </div>
      )}

      {/* Show partial results */}
      {(stats1 && !stats2) && (
        <p className="text-muted-foreground text-sm">
          {isFr ? 'Entre un deuxième pseudo pour comparer.' : 'Enter a second username to compare.'}
        </p>
      )}
    </div>
  )
}
```

- [ ] **Step 2: TypeScript check**

```bash
cd web && npx tsc --noEmit 2>&1 | head -20
```

Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add "web/src/app/[locale]/compare/page.tsx"
git commit -m "feat(web): add /compare page — side-by-side user stats (no auth)"
```

---

## Task 7: Web `/top-weekly` page

**Files:**
- Create: `web/src/app/[locale]/top-weekly/page.tsx`

Shows weekly XP top 10 (from `/xp/leaderboard?period=weekly`) + all-time top messages top 10. Weekly messages doesn't exist — using all-time is the best available approximation.

- [ ] **Step 1: Create `web/src/app/[locale]/top-weekly/page.tsx`**

```tsx
import type { Metadata } from 'next'
import Image from 'next/image'
import { serverLeaderboardXpWeekly, serverLeaderboardMessages } from '@/lib/server-api'

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>
}): Promise<Metadata> {
  const { locale } = await params
  return {
    title: locale === 'fr' ? 'Top Semaine' : 'Weekly Top',
    description:
      locale === 'fr'
        ? 'Classement hebdomadaire XP et top messages de la communauté SaucisseLand.'
        : 'Weekly XP ranking and top messages for the SaucisseLand community.',
  }
}

const MEDALS = ['🥇', '🥈', '🥉']

export default async function TopWeeklyPage({
  params,
}: {
  params: Promise<{ locale: string }>
}) {
  const { locale } = await params
  const isFr = locale === 'fr'

  const [weeklyXp, topMessages] = await Promise.all([
    serverLeaderboardXpWeekly(10),
    serverLeaderboardMessages(1, 10),
  ])

  return (
    <div className="container mx-auto px-4 py-12 max-w-4xl">
      <h1 className="text-3xl font-extrabold tracking-tight mb-2">
        🏆 {isFr ? 'Top de la semaine' : 'Weekly Top'}
      </h1>
      <p className="text-muted-foreground mb-10">
        {isFr
          ? 'Les membres les plus actifs depuis le début de la semaine.'
          : 'The most active members since the start of the week.'}
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        {/* Weekly XP */}
        <section>
          <h2 className="text-lg font-bold mb-4">⚡ {isFr ? 'XP cette semaine' : 'XP this week'}</h2>
          <div className="glass-card divide-y divide-border/20">
            {weeklyXp.length === 0 && (
              <p className="p-4 text-muted-foreground text-sm">
                {isFr ? 'Aucune donnée.' : 'No data.'}
              </p>
            )}
            {weeklyXp.map((entry, i) => (
              <div key={entry.user_id} className="flex items-center gap-3 px-4 py-3">
                <span className="w-7 text-center text-sm font-bold">
                  {MEDALS[i] ?? `${i + 1}`}
                </span>
                {entry.discord_avatar ? (
                  <Image
                    src={entry.discord_avatar}
                    alt={entry.username}
                    width={32}
                    height={32}
                    className="rounded-full flex-shrink-0"
                  />
                ) : (
                  <div className="w-8 h-8 rounded-full bg-accent/20 flex items-center justify-center text-xs font-bold flex-shrink-0">
                    {entry.username[0]?.toUpperCase()}
                  </div>
                )}
                <span className="flex-1 font-medium truncate">{entry.username}</span>
                <span className="text-accent font-bold tabular-nums text-sm">
                  +{entry.weekly_xp.toLocaleString()} XP
                </span>
              </div>
            ))}
          </div>
        </section>

        {/* Top messages */}
        <section>
          <h2 className="text-lg font-bold mb-4">
            💬 {isFr ? 'Top messages (tout temps)' : 'Top messages (all time)'}
          </h2>
          <div className="glass-card divide-y divide-border/20">
            {topMessages.leaderboard.length === 0 && (
              <p className="p-4 text-muted-foreground text-sm">
                {isFr ? 'Aucune donnée.' : 'No data.'}
              </p>
            )}
            {topMessages.leaderboard.map((entry, i) => (
              <div key={entry.user_id} className="flex items-center gap-3 px-4 py-3">
                <span className="w-7 text-center text-sm font-bold">
                  {MEDALS[i] ?? `${i + 1}`}
                </span>
                {entry.discord_avatar ? (
                  <Image
                    src={entry.discord_avatar}
                    alt={entry.username}
                    width={32}
                    height={32}
                    className="rounded-full flex-shrink-0"
                  />
                ) : (
                  <div className="w-8 h-8 rounded-full bg-accent/20 flex items-center justify-center text-xs font-bold flex-shrink-0">
                    {entry.username[0]?.toUpperCase()}
                  </div>
                )}
                <span className="flex-1 font-medium truncate">{entry.username}</span>
                <span className="text-muted-foreground font-bold tabular-nums text-sm">
                  {entry.total_messages.toLocaleString()} msg
                </span>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  )
}
```

Note: `serverLeaderboardMessages(page, limit)` is an existing function in server-api.ts that takes `(page, limit, search?)`. Pass `(1, 10)` for page 1, 10 results.

- [ ] **Step 2: TypeScript check**

```bash
cd web && npx tsc --noEmit 2>&1 | head -20
```

Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add "web/src/app/[locale]/top-weekly/page.tsx"
git commit -m "feat(web): add /top-weekly page — weekly XP + all-time messages top 10"
```

---

## Task 8: Build + push

- [ ] **Step 1: Full TypeScript check**

```bash
cd web && npx tsc --noEmit 2>&1 | grep "error TS"
```

Expected: no output (no errors). `<img>` warnings from admin/editor pages are acceptable.

- [ ] **Step 2: Build**

```bash
cd web && npm run build 2>&1 | tail -30
```

Expected: build completes. Look for `/fr/compare`, `/en/compare`, `/fr/top-weekly`, `/en/top-weekly` in the output as new routes.

- [ ] **Step 3: Quick smoke test — compare page route**

```bash
cd web && npm start &
sleep 4
curl -s "http://localhost:3000/fr/compare" | grep -o '<title>[^<]*</title>'
kill %1
```

Expected: `<title>Comparer · Hermes</title>`

- [ ] **Step 4: Push to main**

```bash
git checkout main && git pull origin main
git merge dev --no-ff -m "feat: bot parité — /achievements, heatmap, /compare, /top-weekly"
git push origin main
git checkout dev
```
