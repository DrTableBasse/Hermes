# Profile Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the activity heatmap, replace the achievements section with a filterable/paginated panel showing locked and unlocked achievements, and add a persistent light/dark theme toggle.

**Architecture:** Three independent features sharing one deploy. Achievements use a new unauthenticated API endpoint (LEFT JOIN to get all achievements + unlock status), a `"use client"` `AchievementsPanel` component (category filter + pagination, 12/page), and minimal changes to the profile page. Theme uses `next-themes` with a `ThemeProvider` wrapper, a `ThemeToggle` button in the Navbar, and a `.light` CSS class added to `globals.css` — `darkMode: ['class']` is already set in `tailwind.config.ts`.

**Tech Stack:** FastAPI + asyncpg (web-api), Next.js 15 App Router, TypeScript, Tailwind CSS, `next-themes` (new dep), `next-intl`.

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `web-api/routes/users.py` | Modify | Add `GET /users/{user_id}/achievements` — all achievements with unlock status |
| `web/src/lib/api.ts` | Modify | Add `AchievementWithStatus` interface |
| `web/src/lib/server-api.ts` | Modify | Add `serverGetUserAchievementsAll` |
| `web/src/components/AchievementsPanel.tsx` | Create | Client component — category filter + pagination |
| `web/src/app/[locale]/profile/page.tsx` | Modify | Remove heatmap + ActivityHeatmap; use AchievementsPanel |
| `web/src/app/globals.css` | Modify | Add `.light` CSS variables |
| `web/src/components/ThemeProvider.tsx` | Create | next-themes wrapper (Client Component) |
| `web/src/components/ThemeToggle.tsx` | Create | Sun/moon button (Client Component) |
| `web/src/app/[locale]/layout.tsx` | Modify | Wrap with ThemeProvider; remove hardcoded `dark` class |
| `web/src/components/Navbar.tsx` | Modify | Add ThemeToggle next to locale switch |
| `web/package.json` + `web/package-lock.json` | Modify | Add `next-themes` dependency |

---

### Task 1: New achievements endpoint — all with unlock status

**Files:**
- Modify: `web-api/routes/users.py`

Context: The existing `GET /users/{user_id}/stats` returns only unlocked achievements. We need a new endpoint that LEFT JOINs to return ALL achievements with an `unlocked` boolean and nullable `unlocked_at`.

- [ ] **Step 1: Read the end of `web-api/routes/users.py`**

```bash
cat web-api/routes/users.py
```

- [ ] **Step 2: Append the new endpoint**

Add this at the END of `web-api/routes/users.py`, after the existing `get_user_public_stats` function:

```python
@router.get("/{user_id}/achievements")
@limiter.limit("60/minute")
async def get_user_achievements_all(request: Request, user_id: int):
    """All achievements with unlock status — unauthenticated."""
    rows = await db.fetch("""
        SELECT
            a.id, a.name, a.description, a.icon, a.points, a.condition_type,
            CASE WHEN ua.user_id IS NOT NULL THEN true ELSE false END AS unlocked,
            ua.unlocked_at
        FROM achievements a
        LEFT JOIN user_achievements ua
               ON a.id = ua.achievement_id AND ua.user_id = $1
        ORDER BY a.points DESC, a.id
    """, user_id)
    return {
        "achievements": [
            {
                "id":             r["id"],
                "name":           r["name"],
                "description":    r["description"],
                "icon":           r["icon"],
                "points":         r["points"],
                "condition_type": r["condition_type"],
                "unlocked":       r["unlocked"],
                "unlocked_at":    r["unlocked_at"].isoformat() if r["unlocked_at"] else None,
            }
            for r in rows
        ]
    }
```

- [ ] **Step 3: Commit**

```bash
git add web-api/routes/users.py
git commit -m "feat(api): GET /users/{id}/achievements — all with unlock status"
```

---

### Task 2: TypeScript type + server-api function

**Files:**
- Modify: `web/src/lib/api.ts`
- Modify: `web/src/lib/server-api.ts`

- [ ] **Step 1: Add `AchievementWithStatus` to `web/src/lib/api.ts`**

Read the file to find the existing `Achievement` interface. Add this new interface right after it:

```typescript
export interface AchievementWithStatus {
  id: number
  name: string
  description: string
  icon: string
  points: number
  condition_type: string
  unlocked: boolean
  unlocked_at: string | null
}
```

- [ ] **Step 2: Add import + function to `web/src/lib/server-api.ts`**

At the top import from `./api`, add `AchievementWithStatus` to the existing import line:
```typescript
import type { ..., AchievementWithStatus } from './api'
```

At the end of the file, add:
```typescript
export async function serverGetUserAchievementsAll(userId: string): Promise<AchievementWithStatus[]> {
  const res = await get<{ achievements: AchievementWithStatus[] }>(`/users/${userId}/achievements`)
  return res.achievements
}
```

- [ ] **Step 3: TypeScript check**

```bash
cd web && npx tsc --noEmit 2>&1 | head -20
```
Expected: 0 errors.

- [ ] **Step 4: Commit**

```bash
git add web/src/lib/api.ts web/src/lib/server-api.ts
git commit -m "feat(types): AchievementWithStatus + serverGetUserAchievementsAll"
```

---

### Task 3: AchievementsPanel client component

**Files:**
- Create: `web/src/components/AchievementsPanel.tsx`

Context: This is a `"use client"` component. It receives ALL achievements (locked + unlocked) and handles filtering by category and pagination locally. CSS classes in use across the codebase: `glass-card`, `glass-card-hover`, `text-muted-foreground`, `text-primary`.

Tier logic (for badge color): `points >= 100` → Légendaire (⭐ yellow), `>= 50` → Épique (💎 indigo), `>= 25` → Rare (🔶 orange), else Commun (⚪ neutral).

Category mapping from `condition_type`:
- `messages` → `'Messages'`
- `voice_hours`, `voice_night_minutes`, `voice_morning_minutes`, `longest_session_minutes`, `unique_voice_channels`, `total_voice_sessions`, `consecutive_voice_days` → `'Vocal'`
- `level`, `xp_total` → `'XP & Niveaux'`
- `bump_count` → `'Bumps'`
- `invites` → `'Invitations'`
- `warn_free` → `'Modération'`
- `streaks` → `'Streaks'`
- anything else → `'Divers'`

- [ ] **Step 1: Create the file**

Create `web/src/components/AchievementsPanel.tsx`:

```tsx
'use client'

import { useState, useMemo } from 'react'
import type { AchievementWithStatus } from '@/lib/api'

const ITEMS_PER_PAGE = 12

const CATEGORY_MAP: Record<string, string> = {
  messages:                'Messages',
  voice_hours:             'Vocal',
  voice_night_minutes:     'Vocal',
  voice_morning_minutes:   'Vocal',
  longest_session_minutes: 'Vocal',
  unique_voice_channels:   'Vocal',
  total_voice_sessions:    'Vocal',
  consecutive_voice_days:  'Vocal',
  level:                   'XP & Niveaux',
  xp_total:                'XP & Niveaux',
  bump_count:              'Bumps',
  invites:                 'Invitations',
  warn_free:               'Modération',
  streaks:                 'Streaks',
}

function getCategory(conditionType: string): string {
  return CATEGORY_MAP[conditionType] ?? 'Divers'
}

function tierBadge(points: number): { label: string; icon: string; cls: string } {
  if (points >= 100) return { label: 'Légendaire', icon: '⭐', cls: 'bg-yellow-500/20 text-yellow-300 ring-yellow-500/40' }
  if (points >= 50)  return { label: 'Épique',     icon: '💎', cls: 'bg-indigo-500/20 text-indigo-300 ring-indigo-500/40' }
  if (points >= 25)  return { label: 'Rare',       icon: '🔶', cls: 'bg-orange-500/20 text-orange-300 ring-orange-500/40' }
  return               { label: 'Commun',     icon: '⚪', cls: 'bg-neutral-500/20 text-neutral-300 ring-neutral-500/40' }
}

interface Props {
  achievements: AchievementWithStatus[]
}

export default function AchievementsPanel({ achievements }: Props) {
  const [category, setCategory] = useState('Tous')
  const [page, setPage]         = useState(1)

  // Build category list from data
  const categories = useMemo(() => {
    const cats = new Set(achievements.map(a => getCategory(a.condition_type)))
    return ['Tous', ...Array.from(cats).sort()]
  }, [achievements])

  // Filter + paginate
  const filtered = useMemo(
    () =>
      category === 'Tous'
        ? achievements
        : achievements.filter(a => getCategory(a.condition_type) === category),
    [achievements, category]
  )

  const totalPages = Math.max(1, Math.ceil(filtered.length / ITEMS_PER_PAGE))
  const currentPage = Math.min(page, totalPages)
  const pageItems = filtered.slice((currentPage - 1) * ITEMS_PER_PAGE, currentPage * ITEMS_PER_PAGE)

  const unlockedCount = achievements.filter(a => a.unlocked).length

  const handleCategory = (cat: string) => {
    setCategory(cat)
    setPage(1)
  }

  return (
    <div>
      {/* Summary */}
      <p className="text-sm text-muted-foreground mb-4">
        {unlockedCount} / {achievements.length} débloqués
      </p>

      {/* Category filter */}
      <div className="flex flex-wrap gap-2 mb-6">
        {categories.map(cat => (
          <button
            key={cat}
            onClick={() => handleCategory(cat)}
            className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
              category === cat
                ? 'bg-primary text-primary-foreground'
                : 'bg-accent text-muted-foreground hover:text-foreground'
            }`}
          >
            {cat}
          </button>
        ))}
      </div>

      {/* Grid */}
      {pageItems.length === 0 ? (
        <div className="glass-card p-8 text-center">
          <p className="text-muted-foreground">Aucun achievement dans cette catégorie.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-6">
          {pageItems.map(a => {
            const tier = tierBadge(a.points)
            return (
              <div
                key={a.id}
                className={`glass-card flex items-start gap-3 p-4 transition-all duration-200 ${
                  a.unlocked
                    ? 'glass-card-hover'
                    : 'opacity-50 grayscale cursor-default'
                }`}
              >
                <span className="text-3xl relative shrink-0">
                  {a.icon}
                  {!a.unlocked && (
                    <span className="absolute -bottom-1 -right-1 text-sm">🔒</span>
                  )}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="font-semibold">{a.name}</p>
                  <p className="text-sm text-muted-foreground">{a.description}</p>
                  <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                    <span className={`text-xs px-2 py-0.5 rounded-full ring-1 font-medium ${tier.cls}`}>
                      {tier.icon} {tier.label}
                    </span>
                    <span className="text-xs text-primary font-medium">+{a.points} pts</span>
                    {a.unlocked && a.unlocked_at && (
                      <span className="text-xs text-muted-foreground">
                        {new Date(a.unlocked_at).toLocaleDateString('fr-FR')}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <button
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={currentPage === 1}
            className="px-3 py-1.5 rounded-lg text-sm bg-accent hover:bg-accent/80 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            ←
          </button>
          <span className="text-sm text-muted-foreground">
            {currentPage} / {totalPages}
          </span>
          <button
            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
            disabled={currentPage === totalPages}
            className="px-3 py-1.5 rounded-lg text-sm bg-accent hover:bg-accent/80 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            →
          </button>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: TypeScript check**

```bash
cd web && npx tsc --noEmit 2>&1 | head -20
```
Expected: 0 errors.

- [ ] **Step 3: Commit**

```bash
git add web/src/components/AchievementsPanel.tsx
git commit -m "feat(web): AchievementsPanel — category filter + pagination + locked state"
```

---

### Task 4: Update profile page — remove heatmap, use AchievementsPanel

**Files:**
- Modify: `web/src/app/[locale]/profile/page.tsx`

Context: The profile page currently imports `ActivityHeatmap` and `serverGetUserActivity`, fetches activity data, and renders it in an `{/* Activité */}` section. It also destructures `achievements` from `data` and renders them manually. Both need to be replaced.

- [ ] **Step 1: Read the full profile page**

```bash
cat web/src/app/[locale]/profile/page.tsx
```

- [ ] **Step 2: Update imports**

Replace:
```typescript
import ActivityHeatmap from '@/components/ActivityHeatmap'
import { serverGetUserStats, serverGetUserActivity } from '@/lib/server-api'
```
With:
```typescript
import AchievementsPanel from '@/components/AchievementsPanel'
import { serverGetUserStats, serverGetUserAchievementsAll } from '@/lib/server-api'
```

- [ ] **Step 3: Replace the activity fetch with achievements fetch**

Find:
```typescript
  let activityData: import('@/lib/api').ActivityDay[] = []
  try { activityData = await serverGetUserActivity(u.discordId) } catch {}
```
Replace with:
```typescript
  let allAchievements: import('@/lib/api').AchievementWithStatus[] = []
  try { allAchievements = await serverGetUserAchievementsAll(u.discordId) } catch {}
```

- [ ] **Step 4: Remove the `{/* Activité */}` section**

Delete the entire block:
```tsx
      {/* Activité */}
      <section className="mb-12">
        <h2 className="text-xl font-bold mb-5">Activité (12 derniers mois)</h2>
        <div className="glass-card p-6">
          <ActivityHeatmap data={activityData} />
        </div>
      </section>
```

- [ ] **Step 5: Replace the `{/* Achievements */}` section**

Find the entire `{/* Achievements */}` section (from `<section>` to its closing `</section>`) and replace it with:

```tsx
      {/* Achievements */}
      <section>
        <h2 className="text-xl font-bold mb-5">{t('achievements')}</h2>
        <AchievementsPanel achievements={allAchievements} />
      </section>
```

Also remove the `achievements` variable from the destructuring line. Find:
```typescript
  const { user: usr, stats, achievements } = data
```
Replace with:
```typescript
  const { user: usr, stats } = data
```

- [ ] **Step 6: TypeScript check**

```bash
cd web && npx tsc --noEmit 2>&1 | head -20
```
Expected: 0 errors.

- [ ] **Step 7: Commit**

```bash
git add web/src/app/[locale]/profile/page.tsx
git commit -m "feat(web): remove heatmap, replace achievements with AchievementsPanel"
```

---

### Task 5: Light theme CSS + install next-themes

**Files:**
- Modify: `web/src/app/globals.css`
- Modify: `web/package.json` + `web/package-lock.json`

- [ ] **Step 1: Install next-themes**

```bash
cd web && npm install next-themes@^0.3.0
```

- [ ] **Step 2: Add `.light` CSS class to `web/src/app/globals.css`**

After the closing `}` of the `:root { ... }` block, add:

```css
  .light {
    --background:   0 0% 98%;
    --foreground:   222 47% 11%;
    --card:         0 0% 100%;
    --card-foreground: 222 47% 11%;
    --primary:      222 47% 11%;
    --primary-foreground: 210 40% 98%;
    --secondary:    210 40% 94%;
    --secondary-foreground: 222 47% 11%;
    --muted:        210 40% 94%;
    --muted-foreground: 215 16% 47%;
    --accent:       210 40% 90%;
    --accent-foreground: 222 47% 11%;
    --destructive:  0 84% 60%;
    --destructive-foreground: 210 40% 98%;
    --border:       214 32% 86%;
    --input:        214 32% 86%;
    --ring:         263 70% 50%;
    --radius:       0.5rem;
    --discord:      235 85.6% 64.7%;
    --gold:         37 90% 55%;
    --success:      142 76% 36%;
    --warning:      38 92% 50%;
  }
```

Note: The `.light` class must be inside `@layer base { }`. Read the file first — the `:root` block is inside `@layer base { }`. Add `.light` inside the same `@layer base { }` block.

- [ ] **Step 3: TypeScript check**

```bash
cd web && npx tsc --noEmit 2>&1 | head -20
```
Expected: 0 errors.

- [ ] **Step 4: Commit**

```bash
git add web/package.json web/package-lock.json web/src/app/globals.css
git commit -m "feat(web): add next-themes dep + light theme CSS variables"
```

---

### Task 6: ThemeProvider + ThemeToggle + layout + Navbar

**Files:**
- Create: `web/src/components/ThemeProvider.tsx`
- Create: `web/src/components/ThemeToggle.tsx`
- Modify: `web/src/app/[locale]/layout.tsx`
- Modify: `web/src/components/Navbar.tsx`

- [ ] **Step 1: Create `web/src/components/ThemeProvider.tsx`**

```tsx
'use client'

import { ThemeProvider as NextThemesProvider } from 'next-themes'

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  return (
    <NextThemesProvider attribute="class" defaultTheme="dark" enableSystem={false}>
      {children}
    </NextThemesProvider>
  )
}
```

- [ ] **Step 2: Create `web/src/components/ThemeToggle.tsx`**

```tsx
'use client'

import { useTheme } from 'next-themes'
import { useEffect, useState } from 'react'

export function ThemeToggle() {
  const { theme, setTheme } = useTheme()
  const [mounted, setMounted] = useState(false)
  useEffect(() => setMounted(true), [])

  // Render placeholder during SSR to avoid hydration mismatch
  if (!mounted) return <div className="w-9 h-9" />

  return (
    <button
      onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
      className="w-9 h-9 flex items-center justify-center rounded-lg hover:bg-accent transition-colors text-lg"
      aria-label="Changer le thème"
    >
      {theme === 'dark' ? '☀️' : '🌙'}
    </button>
  )
}
```

- [ ] **Step 3: Update `web/src/app/[locale]/layout.tsx`**

Read the file. Make two changes:

**Change A** — Add import at the top:
```typescript
import { ThemeProvider } from '@/components/ThemeProvider'
```

**Change B** — Replace:
```tsx
    <html lang={locale} className="dark">
      <body>
        <NextIntlClientProvider messages={messages}>
```
With:
```tsx
    <html lang={locale} suppressHydrationWarning>
      <body>
        <ThemeProvider>
        <NextIntlClientProvider messages={messages}>
```
And close the `<ThemeProvider>` before `</body>`:
Find `</NextIntlClientProvider>` and the line after it (`</body>`) — add `</ThemeProvider>` between them:
```tsx
        </NextIntlClientProvider>
        </ThemeProvider>
      </body>
```

- [ ] **Step 4: Add ThemeToggle to `web/src/components/Navbar.tsx`**

Read the file. 

Add import at the top:
```typescript
import { ThemeToggle } from '@/components/ThemeToggle'
```

Find the locale switch button (a `<button>` that calls `switchLocale()`). Add `<ThemeToggle />` directly next to it:
```tsx
<ThemeToggle />
<button onClick={switchLocale} ...>
  {locale === 'fr' ? '🇬🇧' : '🇫🇷'}
</button>
```

Apply the same pattern in the mobile menu section if the locale button appears there too.

- [ ] **Step 5: TypeScript check**

```bash
cd web && npx tsc --noEmit 2>&1 | head -20
```
Expected: 0 errors.

- [ ] **Step 6: Commit**

```bash
git add web/src/components/ThemeProvider.tsx web/src/components/ThemeToggle.tsx web/src/app/[locale]/layout.tsx web/src/components/Navbar.tsx
git commit -m "feat(web): light/dark theme toggle with next-themes"
```

---

### Task 7: Build, merge to main, deploy to production

- [ ] **Step 1: Final TypeScript check**

```bash
cd web && npx tsc --noEmit
```
Expected: 0 errors.

- [ ] **Step 2: Merge dev → main**

```bash
git checkout main
git pull
git merge dev --no-ff -m "feat: profile overhaul — achievements panel, theme toggle, heatmap removal"
git push origin main
```

- [ ] **Step 3: Deploy to production**

Save as `deploy.py` and run with Python:
```python
import paramiko, sys

host, user, pwd, path = '192.168.10.62', 'ubuntu', 'Soldat21*/!!', '/home/ubuntu/Hermes-v2'
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(host, username=user, password=pwd, timeout=15)

def run(cmd, timeout=420):
    _, out, err = client.exec_command(cmd, timeout=timeout)
    o = out.read().decode('utf-8', errors='replace')
    e = err.read().decode('utf-8', errors='replace')
    if o: sys.stdout.buffer.write(o[-5000:].encode('utf-8', errors='replace'))

run(f'echo "{pwd}" | sudo -S bash -c "cd {path} && git pull origin main && docker compose up --build -d" 2>&1')
client.close()
```

- [ ] **Step 4: Verify containers**

Expected: 4 hermes containers `(healthy)`.

---

## Self-Review

**Spec coverage:**
- ✅ Remove heatmap — Task 4 (removes import, fetch, section)
- ✅ Achievements locked/unlocked — Task 1 (API LEFT JOIN) + Task 3 (panel, greyed locked items with 🔒)
- ✅ Pagination — Task 3 (`ITEMS_PER_PAGE = 12`, prev/next buttons)
- ✅ Category filter — Task 3 (category buttons, CATEGORY_MAP)
- ✅ Light theme — Task 5 (`.light` CSS vars) + Task 6 (ThemeProvider, defaultTheme dark)
- ✅ Dark theme (existing, preserved as default)
- ✅ Toggle button — Task 6 (ThemeToggle in Navbar)
- ✅ Persistent preference — next-themes stores in localStorage automatically

**Type consistency:**
- `AchievementWithStatus` defined in Task 2, used in Task 3 (`Props`) and Task 4 (`allAchievements`)
- `serverGetUserAchievementsAll` defined in Task 2, called in Task 4
- `ThemeProvider` defined in Task 6 step 1, imported in layout step 3
- `ThemeToggle` defined in Task 6 step 2, imported in Navbar step 4

**No placeholders:** All code blocks are complete.
