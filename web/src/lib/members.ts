import type { Grade, LbPage, PublicGrade } from "@/lib/api/types"
import { formatNumber } from "@/lib/format"

// ── Classement : onglets et lignes ───────────────────────────────────────────

export const RANK_TABS = ["global", "voice", "messages", "achievements", "bumps", "invites", "levels", "streaks"] as const
export type RankTab = (typeof RANK_TABS)[number]

export const RANK_TAB_LABELS: Record<RankTab, string> = {
  global: "Global",
  voice: "Vocal",
  messages: "Messages",
  achievements: "Succès",
  bumps: "Bumps",
  invites: "Invitations",
  levels: "Niveaux",
  streaks: "Séries",
}

/** Paramètre d'URL : Next fournit `string | string[]` (`?q=a&q=b`) ; on garde la première valeur. */
export function firstParam(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value
}

/** Onglet demandé dans l'URL ; toute valeur inconnue retombe sur le classement global. */
export function parseTab(raw: string | undefined): RankTab {
  return RANK_TABS.find(t => t === raw) ?? "global"
}

/** Numéro de page demandé : entier ≥ 1, sinon 1. */
export function parsePage(raw: string | undefined): number {
  const n = Number.parseInt(raw ?? "", 10)
  return Number.isFinite(n) && n >= 1 ? n : 1
}

/** Ligne d'un classement, indépendante de la catégorie. Les identifiants restent des chaînes. */
export interface RankRow {
  id: string
  rank: number
  name: string
  avatar: string | null
  grade: PublicGrade | null
  level: number | null
  /** Score principal de la catégorie (« 1 234 msgs », « 12h 3m »…). */
  score: string
  /** Détail secondaire (multiplicateur de série). */
  detail?: string
}

type AnyEntry = LbPage<unknown>["leaderboard"][number] & {
  user_id: string
  username: string
  discord_avatar: string | null
  global_rank: number
  formatted?: string
  global_score?: number
  total_messages?: number
  bump_count?: number
  invite_count?: number
  achievement_count?: number
  current_level?: number
  total_xp?: number
  grade?: PublicGrade
  current_streak?: number
  max_streak?: number
  xp_multiplier?: number
}

function score(tab: RankTab, e: AnyEntry): { score: string; detail?: string } {
  switch (tab) {
    case "global":
      return { score: `${formatNumber(e.global_score ?? 0)} pts` }
    case "voice":
      return { score: e.formatted ?? "—" }
    case "messages":
      return { score: `${formatNumber(e.total_messages ?? 0)} msgs` }
    case "bumps":
      return { score: `${formatNumber(e.bump_count ?? 0)} bumps` }
    case "invites":
      return { score: `${formatNumber(e.invite_count ?? 0)} invitations` }
    case "levels":
      return { score: `${formatNumber(e.total_xp ?? 0)} XP` }
    case "streaks":
      return {
        score: `${e.current_streak ?? 0} j · record ${e.max_streak ?? 0} j`,
        detail: `×${Number(e.xp_multiplier ?? 1).toFixed(1)}`,
      }
    case "achievements":
      return { score: `${formatNumber(e.achievement_count ?? 0)} succès` }
  }
}

/** Entrées d'un onglet → lignes affichables ; seul l'onglet « niveaux » porte grade et niveau. */
export function toRankRows(tab: RankTab, entries: readonly object[]): RankRow[] {
  return (entries as AnyEntry[]).map(e => ({
    id: e.user_id,
    rank: e.global_rank,
    name: e.username,
    avatar: e.discord_avatar,
    grade: tab === "levels" ? (e.grade ?? null) : null,
    level: tab === "levels" ? (e.current_level ?? null) : null,
    ...score(tab, e),
  }))
}

/** Page du classement où se trouve le rang `rank`. */
export function pageOfRank(rank: number, limit: number): number {
  return Math.max(1, Math.ceil(rank / limit))
}

/** Pages à afficher : première, dernière et ±2 autour de la courante ; `"gap"` pour chaque trou de 2 pages ou plus. */
export function pageWindow(page: number, totalPages: number): Array<number | "gap"> {
  const visible = new Set<number>([1, totalPages])
  for (let p = Math.max(1, page - 2); p <= Math.min(totalPages, page + 2); p++) visible.add(p)
  const sorted = [...visible].sort((a, b) => a - b)
  const out: Array<number | "gap"> = []
  sorted.forEach((p, i) => {
    const prev = sorted[i - 1]
    if (i > 0 && p - prev === 2) out.push(prev + 1)
    else if (i > 0 && p - prev > 2) out.push("gap")
    out.push(p)
  })
  return out
}

// ── Grades ───────────────────────────────────────────────────────────────────

/** Dernier grade dont `level_min ≤ max(niveau, 1)` (même règle que `web-api/grades.py`) ; `null` sans liste. */
export function gradeForLevel(level: number, grades: Grade[] | null): PublicGrade | null {
  if (!grades || grades.length === 0) return null
  const sorted = [...grades].sort((a, b) => a.level_min - b.level_min)
  const lvl = Math.max(level || 0, 1)
  let current = sorted[0]
  for (const g of sorted) if (g.level_min <= lvl) current = g
  return { name: current.name, slug: current.slug, color: current.color }
}

// ── Succès ───────────────────────────────────────────────────────────────────

const CATEGORY: Record<string, string> = {
  messages: "Messages",
  voice_hours: "Vocal",
  voice_night_minutes: "Vocal",
  voice_morning_minutes: "Vocal",
  longest_session_minutes: "Vocal",
  unique_voice_channels: "Vocal",
  total_voice_sessions: "Vocal",
  consecutive_voice_days: "Vocal",
  level: "XP & Niveaux",
  xp_total: "XP & Niveaux",
  bump_count: "Bumps",
  invites: "Invitations",
  warn_free: "Modération",
  streaks: "Séries",
}

export function achievementCategory(conditionType: string): string {
  return CATEGORY[conditionType] ?? "Divers"
}

// ── Erreurs d'API ────────────────────────────────────────────────────────────

/**
 * Membre inconnu pour web-api : 404, ou 422 quand l'identifiant n'est pas un entier. Les erreurs de
 * `server.ts` portent le statut en tête du message (« 404 /users/… »).
 */
export function isUnknownMember(error: unknown): boolean {
  return error instanceof Error && /^(404|422) /.test(error.message)
}

/** Identifiant Discord plausible (entier décimal) ; le reste ne vaut même pas un appel à web-api. */
export function isSnowflake(value: string): boolean {
  return /^\d{1,20}$/.test(value)
}
