import 'server-only'
import type { Article, ArticleList, Tag, VoiceEntry, LeaderboardEntry, ActivityDay, XPEntry, Achievement, AchievementWithStatus } from './api'

const WEB_API = process.env.WEB_API_INTERNAL_URL ?? 'http://web-api:8000'

async function get<T>(path: string, token?: string): Promise<T> {
  const headers: Record<string, string> = {}
  if (token) headers['Cookie'] = `better-auth.session_token=${token}`
  const r = await fetch(`${WEB_API}${path}`, { headers, cache: 'no-store' })
  if (!r.ok) throw new Error(`${r.status} ${path}`)
  return r.json()
}

// ── Articles ──────────────────────────────────────────────────────────────────

export async function serverListArticles(params: {
  page?: number; limit?: number; tag?: string; search?: string
}): Promise<ArticleList> {
  const qs = new URLSearchParams()
  if (params.page)   qs.set('page',   String(params.page))
  if (params.limit)  qs.set('limit',  String(params.limit))
  if (params.tag)    qs.set('tag',    params.tag)
  if (params.search) qs.set('search', params.search)
  return get<ArticleList>(`/articles?${qs}`)
}

export async function serverListTags(): Promise<Tag[]> {
  const data = await get<{ tags: Tag[] }>('/tags')
  return data.tags
}

export async function serverGetArticle(slug: string, token?: string): Promise<Article> {
  return get<Article>(`/articles/${slug}`, token)
}

export async function serverMyArticles(token: string): Promise<Article[]> {
  const data = await get<{ articles: Article[] }>('/articles/mine', token)
  return data.articles
}

// ── Users ─────────────────────────────────────────────────────────────────────

export async function serverGetUserStats(userId: string, token: string): Promise<import('./api').UserStats> {
  return get<import('./api').UserStats>(`/users/${userId}/stats`, token)
}

// ── Leaderboard ───────────────────────────────────────────────────────────────

export interface LbPage<T> { leaderboard: T[]; total: number; page: number; limit: number }
export interface AchievementEntry { user_id: string; username: string; discord_avatar: string | null; achievement_count: number }
export interface BumpEntry       { user_id: string; username: string; discord_avatar: string | null; bump_count: number; global_rank: number }
export interface InviteEntry     { user_id: string; username: string; discord_avatar: string | null; invite_count: number; global_rank: number }
export interface LevelEntry  { user_id: string; username: string; discord_avatar: string | null; current_level: number; total_xp: number; global_rank: number }
export interface StreakEntry { user_id: string; username: string; discord_avatar: string | null; current_streak: number; max_streak: number; xp_multiplier: number; global_rank: number }
export interface MyRanks { voice_rank: number; messages_rank: number; achievements_rank: number; bumps_rank: number; invites_rank: number; level_rank: number; streak_rank: number }

export async function serverLeaderboardVoice(page = 1, limit = 5, search?: string): Promise<LbPage<VoiceEntry>> {
  const qs = new URLSearchParams({ page: String(page), limit: String(limit) })
  if (search) qs.set('search', search)
  return get<LbPage<VoiceEntry>>(`/leaderboard/voice?${qs}`)
}

export async function serverLeaderboardMessages(page = 1, limit = 5, search?: string): Promise<LbPage<LeaderboardEntry>> {
  const qs = new URLSearchParams({ page: String(page), limit: String(limit) })
  if (search) qs.set('search', search)
  return get<LbPage<LeaderboardEntry>>(`/leaderboard/messages?${qs}`)
}

export async function serverLeaderboardAchievements(page = 1, limit = 5, search?: string): Promise<LbPage<AchievementEntry>> {
  const qs = new URLSearchParams({ page: String(page), limit: String(limit) })
  if (search) qs.set('search', search)
  return get<LbPage<AchievementEntry>>(`/leaderboard/achievements?${qs}`)
}

export async function serverLeaderboardBumps(page = 1, limit = 5, search?: string): Promise<LbPage<BumpEntry>> {
  const qs = new URLSearchParams({ page: String(page), limit: String(limit) })
  if (search) qs.set('search', search)
  return get<LbPage<BumpEntry>>(`/leaderboard/bumps?${qs}`)
}

export async function serverLeaderboardInvites(page = 1, limit = 5, search?: string): Promise<LbPage<InviteEntry>> {
  const qs = new URLSearchParams({ page: String(page), limit: String(limit) })
  if (search) qs.set('search', search)
  return get<LbPage<InviteEntry>>(`/leaderboard/invites?${qs}`)
}

export async function serverLeaderboardLevels(page = 1, limit = 5, search?: string): Promise<LbPage<LevelEntry>> {
  const qs = new URLSearchParams({ page: String(page), limit: String(limit) })
  if (search) qs.set('search', search)
  return get<LbPage<LevelEntry>>(`/leaderboard/levels?${qs}`)
}

export async function serverLeaderboardStreaks(page = 1, limit = 5, search?: string): Promise<LbPage<StreakEntry>> {
  const qs = new URLSearchParams({ page: String(page), limit: String(limit) })
  if (search) qs.set('search', search)
  return get<LbPage<StreakEntry>>(`/leaderboard/streaks?${qs}`)
}

export async function serverMyRanks(token: string): Promise<MyRanks> {
  return get<MyRanks>('/leaderboard/me', token)
}

export interface GlobalEntry {
  user_id: string; username: string; discord_avatar: string | null
  voice_formatted: string; total_messages: number; achievement_count: number; global_score: number
}

export async function serverLeaderboardGlobal(limit = 5): Promise<GlobalEntry[]> {
  const data = await get<LbPage<GlobalEntry>>(`/leaderboard/global?limit=${limit}`)
  return data.leaderboard
}

// kept for home page (limit=5, no pagination)
export async function serverListVoiceLeaderboard(limit = 5): Promise<VoiceEntry[]> {
  const data = await get<LbPage<VoiceEntry>>(`/leaderboard/voice?limit=${limit}`)
  return data.leaderboard
}

export async function serverListMessagesLeaderboard(limit = 20): Promise<LeaderboardEntry[]> {
  const data = await get<LbPage<LeaderboardEntry>>(`/leaderboard/messages?limit=${limit}`)
  return data.leaderboard
}

export interface PublicUserStats {
  user_id: string
  username: string
  nickname: string | null
  discord_avatar: string | null
  stats: {
    total_messages: number
    voice_seconds: number
    voice_formatted: string
    total_xp: number
    current_level: number
    achievement_count: number
    current_streak: number
    bump_count: number
  }
  achievements: Achievement[]
}

export async function serverGetUserPublicStats(userId: string): Promise<PublicUserStats> {
  return get<PublicUserStats>(`/users/${userId}/public`)
}

export async function serverGetUserActivity(userId: string): Promise<ActivityDay[]> {
  const res = await get<{ heatmap: ActivityDay[] }>(`/activity/${userId}/heatmap?days=365`)
  return res.heatmap
}

export async function serverSearchUserByUsername(
  query: string
): Promise<LbPage<LeaderboardEntry>> {
  return get<LbPage<LeaderboardEntry>>(
    `/leaderboard/messages?search=${encodeURIComponent(query)}&limit=1`
  )
}

export async function serverLeaderboardXpWeekly(limit = 10): Promise<LbPage<XPEntry>> {
  return get<LbPage<XPEntry>>(`/xp/leaderboard?period=weekly&limit=${limit}`)
}

export async function serverGetUserAchievementsAll(userId: string): Promise<AchievementWithStatus[]> {
  const res = await get<{ achievements: AchievementWithStatus[] }>(`/users/${userId}/achievements`)
  return res.achievements
}
