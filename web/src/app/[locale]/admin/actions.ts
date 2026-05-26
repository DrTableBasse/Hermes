'use server'
import { headers } from 'next/headers'
import { auth } from '@/lib/auth'

const WEB_API = process.env.WEB_API_INTERNAL_URL ?? 'http://web-api:8000'

export type Result<T = null> =
  | { ok: true;  data: T }
  | { ok: false; error: string }

async function getToken(): Promise<string | null> {
  try {
    const session = await auth.api.getSession({ headers: await headers() })
    return session ? (session.session as any).token as string : null
  } catch {
    return null
  }
}

async function apiFetch<T = null>(
  path: string,
  method = 'GET',
  body?: object,
): Promise<Result<T>> {
  try {
    const token = await getToken()
    if (!token) return { ok: false, error: 'Non authentifié' }

    const r = await fetch(`${WEB_API}${path}`, {
      method,
      headers: {
        'Content-Type': 'application/json',
        Cookie: `better-auth.session_token=${token}`,
      },
      ...(body ? { body: JSON.stringify(body) } : {}),
    })

    if (!r.ok) {
      const err = await r.json().catch(() => ({ detail: r.statusText }))
      return { ok: false, error: err.detail ?? `Erreur ${r.status}` }
    }

    if (r.status === 204) return { ok: true, data: null as T }
    return { ok: true, data: (await r.json()) as T }
  } catch (e: any) {
    return { ok: false, error: e?.message ?? 'Erreur réseau' }
  }
}


// ── Moderation actions ────────────────────────────────────────────────────────

export async function actionWarn(userId: string, reason: string): Promise<Result> {
  return apiFetch('/admin/warns', 'POST', { user_id: userId, reason })
}

export async function actionKick(userId: string, reason: string): Promise<Result> {
  return apiFetch('/admin/kick', 'POST', { user_id: userId, reason })
}

export async function actionBan(userId: string, reason: string): Promise<Result> {
  return apiFetch('/admin/ban', 'POST', { user_id: userId, reason })
}

export async function actionTimeout(userId: string, reason: string, duration: number): Promise<Result> {
  return apiFetch('/admin/timeout', 'POST', { user_id: userId, reason, duration })
}

export async function actionToggleCommand(name: string, enabled: boolean): Promise<Result> {
  return apiFetch('/admin/commands/toggle', 'POST', { command_name: name, enabled })
}


// ── User search ───────────────────────────────────────────────────────────────

export interface UserResult {
  user_id: string
  username: string
  discord_avatar: string | null
}

export async function searchUsers(query: string): Promise<UserResult[]> {
  if (query.length < 2) return []
  const result = await apiFetch<{ users: UserResult[] }>(
    `/admin/users/search?q=${encodeURIComponent(query)}`,
  )
  return result.ok ? (result.data.users ?? []) : []
}


// ── User profile & warns ──────────────────────────────────────────────────────

export interface WarnEntry {
  id: number
  user_id: string
  reason: string
  create_time: number
  moderator_id: string
  moderator_username: string | null
}

export interface UserProfile {
  user: {
    user_id: number
    username: string
    nickname: string | null
    discord_avatar: string | null
    last_seen: string | null
  }
  stats: {
    total_messages: number
    voice_hours: number
    warn_count: number
    msg_rank: number
    voice_rank: number
    xp_total: number
    current_level: number
    current_streak: number
  }
  achievements: Array<{
    id: number
    name: string
    description: string
    icon: string
    points: number
    unlocked_at: string
  }>
}

export async function fetchUserProfile(userId: string): Promise<Result<UserProfile>> {
  return apiFetch<UserProfile>(`/users/${userId}/stats`)
}

export async function fetchUserWarns(userId: string): Promise<Result<WarnEntry[]>> {
  const result = await apiFetch<{ warns: WarnEntry[] }>(`/admin/warns/${userId}`)
  if (!result.ok) return result
  return { ok: true, data: result.data.warns ?? [] }
}

export async function actionDeleteWarn(warnId: number): Promise<Result> {
  return apiFetch(`/admin/warns/${warnId}`, 'DELETE')
}

export interface GlobalWarnEntry {
  id: number
  user_id: string
  username: string
  discord_avatar: string | null
  reason: string
  create_time: number
  moderator_id: string
  moderator_username: string | null
}

export async function fetchAllWarns(): Promise<Result<GlobalWarnEntry[]>> {
  const result = await apiFetch<{ warns: GlobalWarnEntry[] }>('/admin/warns')
  if (!result.ok) return result
  return { ok: true, data: result.data.warns ?? [] }
}

export interface AdminLog {
  id: number
  action_type: string
  actor_id: string | null
  actor_name: string | null
  target_id: string | null
  target_name: string | null
  details: Record<string, unknown>
  created_at: string
}

export interface AdminLogsPage {
  logs: AdminLog[]
  total: number
  page: number
  pages: number
}

export async function fetchAdminLogs(actionType?: string, page = 1): Promise<Result<AdminLogsPage>> {
  const params = new URLSearchParams({ page: String(page) })
  if (actionType) params.set('action_type', actionType)
  return apiFetch<AdminLogsPage>(`/admin/logs?${params}`)
}


// ── Quest templates ───────────────────────────────────────────────────────────

export interface QuestTemplate {
  id:           number
  title:        string
  description:  string | null
  quest_type:   string
  target_value: number
  xp_reward:    number
  icon:         string
  is_enabled:   boolean
  created_at:   string
}

export interface ActiveQuest {
  id:                number
  title:             string
  description:       string | null
  quest_type:        string
  target_value:      number
  xp_reward:         number
  icon:              string
  week_start:        string
  week_end:          string
  is_active:         boolean
  participant_count: number
  completed_count:   number
}

export async function fetchQuestTemplates(): Promise<Result<QuestTemplate[]>> {
  const r = await apiFetch<{ templates: QuestTemplate[] }>('/admin/quest-templates')
  if (!r.ok) return r
  return { ok: true, data: r.data.templates ?? [] }
}

export async function createQuestTemplate(body: Omit<QuestTemplate, 'id' | 'created_at'>): Promise<Result<QuestTemplate>> {
  return apiFetch<QuestTemplate>('/admin/quest-templates', 'POST', body)
}

export async function updateQuestTemplate(id: number, body: Omit<QuestTemplate, 'id' | 'created_at'>): Promise<Result<QuestTemplate>> {
  return apiFetch<QuestTemplate>(`/admin/quest-templates/${id}`, 'PUT', body)
}

export async function deleteQuestTemplate(id: number): Promise<Result> {
  return apiFetch(`/admin/quest-templates/${id}`, 'DELETE')
}

export async function fetchActiveQuests(): Promise<Result<ActiveQuest[]>> {
  const r = await apiFetch<{ quests: ActiveQuest[] }>('/admin/quests/active')
  if (!r.ok) return r
  return { ok: true, data: r.data.quests ?? [] }
}

export async function deployWeeklyQuests(count: number): Promise<Result<{ deployed: number; week_start: string; week_end: string }>> {
  return apiFetch('/admin/quests/deploy', 'POST', { count })
}


// ── Analytics ─────────────────────────────────────────────────────────────────

export interface AnalyticsData {
  actions_14d: Array<{ date: string; label: string; warn: number; kick: number; ban: number; timeout: number }>
  level_distribution: Array<{ level_range: string; count: number }>
  quest_completion: Array<{ title: string; participants: number; completed: number; rate: number }>
  top_xp_weekly: Array<{ username: string; weekly_xp: number }>
  summary: { active_members: number; total_messages: number; warns_30d: number; quests_done_7d: number }
}

export async function fetchAnalytics(): Promise<Result<AnalyticsData>> {
  return apiFetch<AnalyticsData>('/admin/analytics')
}
