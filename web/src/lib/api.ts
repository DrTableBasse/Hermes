// Toujours relatif : le navigateur passe par /api/proxy → Next.js relaie vers web-api (réseau interne)
const API = process.env.NEXT_PUBLIC_API_URL ?? '/api/proxy'

async function request<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...opts.headers },
    ...opts,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? 'API Error')
  }
  return res.json() as Promise<T>
}

// Auth
export const api = {
  auth: {
    me: () => request<User>('/auth/me'),
  },
  users: {
    stats: (id: string) => request<UserStats>(`/users/${id}/stats`),
  },
  leaderboard: {
    messages: (limit = 10) => request<{ leaderboard: LeaderboardEntry[] }>(`/leaderboard/messages?limit=${limit}`),
    voice:    (limit = 10) => request<{ leaderboard: VoiceEntry[] }>(`/leaderboard/voice?limit=${limit}`),
  },
  articles: {
    list:   (page = 1, limit = 12, tag?: string) =>
      request<ArticleList>(`/articles?page=${page}&limit=${limit}${tag ? `&tag=${tag}` : ''}`),
    get:    (slug: string)                 => request<Article>(`/articles/${slug}`),
    create: (data: ArticleCreateInput)    => request<Article>('/articles', { method: 'POST', body: JSON.stringify(data) }),
    update: (id: number, data: Partial<ArticleCreateInput>) =>
      request<Article>(`/articles/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
    delete: (id: number)                  => request(`/articles/${id}`, { method: 'DELETE' }),
  },
  tags: {
    list:   () => request<{ tags: Tag[] }>('/tags'),
    create: (data: TagInput) => request<Tag>('/tags', { method: 'POST', body: JSON.stringify(data) }),
    update: (id: number, data: Partial<TagInput>) =>
      request<Tag>(`/tags/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
    delete: (id: number)    => request(`/tags/${id}`, { method: 'DELETE' }),
  },
  media: {
    upload: (file: File) => {
      const form = new FormData()
      form.append('file', file)
      return fetch(`${API}/media/upload`, { method: 'POST', credentials: 'include', body: form })
        .then(r => r.json() as Promise<{ url: string; filename: string }>)
    },
  },
  admin: {
    stats:          ()            => request<AdminStats>('/admin/stats'),
    commands:       ()            => request<{ commands: Record<string, boolean> }>('/admin/commands'),
    toggleCommand:  (data: CommandToggle) =>
      request('/admin/commands/toggle', { method: 'POST', body: JSON.stringify(data) }),
    kick:           (data: ModerationAction) => request('/admin/kick',    { method: 'POST', body: JSON.stringify(data) }),
    ban:            (data: ModerationAction) => request('/admin/ban',     { method: 'POST', body: JSON.stringify(data) }),
    timeout:        (data: ModerationAction) => request('/admin/timeout', { method: 'POST', body: JSON.stringify(data) }),
    warn:           (data: ModerationAction) => request('/admin/warns',   { method: 'POST', body: JSON.stringify(data) }),
    getWarns:       (userId: string)         => request<{ warns: Warn[] }>(`/admin/warns/${userId}`),
    deleteWarn:     (warnId: number)         => request(`/admin/warns/${warnId}`, { method: 'DELETE' }),
  },
  xp: {
    leaderboard: (period?: string) => request<{ leaderboard: XPEntry[] }>(`/xp/leaderboard${period ? `?period=${period}` : ''}`),
    get: (userId: string) => request<XPData>(`/xp/${userId}`),
  },
  notifications: {
    list: () => request<{ notifications: Notification[] }>('/notifications'),
    markRead: (id: number) => request(`/notifications/${id}/read`, { method: 'POST' }),
    markAllRead: () => request('/notifications/read-all', { method: 'POST' }),
  },
  endorsements: {
    get: (userId: string) => request<{ skills: EndorsementSkill[]; total: number }>(`/endorsements/${userId}`),
    endorse: (data: { target_user_id: number; skill: string }) =>
      request('/endorsements', { method: 'POST', body: JSON.stringify(data) }),
    leaderboard: (limit?: number) => request<{ leaderboard: ReputationEntry[] }>(`/endorsements${limit ? `?limit=${limit}` : ''}`),
  },
  activity: {
    heatmap: (userId: string, days?: number) =>
      request<{ heatmap: ActivityDay[] }>(`/activity/${userId}/heatmap${days ? `?days=${days}` : ''}`),
    daily: (userId: string, days?: number) =>
      request<{ daily: DailyActivity[] }>(`/activity/${userId}/daily${days ? `?days=${days}` : ''}`),
  },
  quests: {
    list: () => request<{ quests: Quest[] }>('/quests'),
    claim: (questId: number) => request<{ success: boolean; xp_reward: number }>(`/quests/${questId}/claim`, { method: 'POST' }),
  },
  comments: {
    list: (articleId: number) => request<{ comments: Comment[] }>(`/comments/article/${articleId}`),
    create: (data: { article_id: number; content: string; parent_id?: number }) =>
      request<Comment>('/comments', { method: 'POST', body: JSON.stringify(data) }),
    delete: (id: number) => request(`/comments/${id}`, { method: 'DELETE' }),
    vote: (id: number) => request<{ voted: boolean }>(`/comments/${id}/vote`, { method: 'POST' }),
  },
}

// ─── Types ────────────────────────────────────────────────────────────────────
export interface User {
  user_id: string; username: string; avatar: string | null
  is_admin: boolean; is_redacteur: boolean
}
export interface UserStats {
  user:    { user_id: number; username: string; nickname: string | null; discord_avatar: string | null; last_seen: string }
  stats:   { total_messages: number; voice_hours: number; warn_count: number; msg_rank: number; voice_rank: number; xp_total: number; current_level: number; current_streak: number; max_streak: number; xp_multiplier: number; bump_count: number; bump_rank: number }
  achievements: Achievement[]
}
export interface Achievement { id: number; name: string; description: string; icon: string; points: number; unlocked_at: string }
export interface LeaderboardEntry { user_id: number; username: string; discord_avatar: string | null; total_messages: number }
export interface VoiceEntry { user_id: number; username: string; discord_avatar: string | null; total_seconds: number; formatted: string }
export interface Tag { id: number; name: string; slug: string; color: string }
export interface TagInput { name: string; color?: string }
export interface Article {
  id: number; author_id: number; title: string; slug: string; content: string
  cover_image_url: string | null; published: boolean; created_at: string; updated_at: string
  tags: Tag[]; author: { user_id: number; username: string; discord_avatar: string | null } | null
}
export interface ArticleList { articles: Article[]; total: number; page: number; limit: number }
export interface ArticleCreateInput { title: string; content: string; cover_image_url?: string; published: boolean; tag_ids: number[] }
export interface AdminStats { members: number; total_messages: number; total_warns: number; total_articles: number }
export interface CommandToggle { command_name: string; enabled: boolean }
export interface ModerationAction { user_id: number; reason?: string; duration?: number }
export interface Warn { id: number; user_id: number; reason: string; create_time: number; moderator_id: number }
export interface XPData { user_id: number; total_xp: number; weekly_xp: number; current_level: number }
export interface XPEntry { user_id: number; username: string; discord_avatar: string | null; total_xp: number; weekly_xp: number; current_level: number }
export interface Notification { id: number; user_id: number; type: string; title: string; body: string; is_read: boolean; created_at: string }
export interface EndorsementSkill { skill: string; count: number }
export interface ReputationEntry { user_id: number; username: string; discord_avatar: string | null; total_endorsements: number }
export interface ActivityDay { date: string; count: number }
export interface DailyActivity { date: string; messages: number }
export interface Quest { id: number; title: string; description: string; quest_type: string; target_value: number; xp_reward: number; current_progress: number; status: string }
export interface Comment { id: number; article_id: number; user_id: number; content: string; parent_id: number | null; vote_count: number; created_at: string; username: string; discord_avatar: string | null }
