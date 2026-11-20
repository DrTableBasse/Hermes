/**
 * Accès à web-api depuis le navigateur. Tout passe par `/api/proxy` : Next.js relaie
 * vers web-api (réseau Docker interne) en transmettant le cookie de session.
 */
import type {
  AdminLogPage,
  AdminStats,
  AdminWarn,
  ActivityDay,
  Article,
  ArticleComment,
  ArticleCreateInput,
  ArticleList,
  CommandToggle,
  DailyActivity,
  Endorsements,
  GameInput,
  GradeInput,
  ModerationAction,
  Notification,
  Ok,
  PageInput,
  QuestClaim,
  Quest,
  QuestTemplate,
  QuestTemplateInput,
  ReputationEntry,
  SessionUser,
  SettingsResponse,
  Snowflake,
  StaffProfileInput,
  Tag,
  TagInput,
  TicketList,
  UserSearchResult,
  Warn,
  XpData,
  XpEntry,
  XpPeriod,
  LbPage,
  VoiceEntry,
  MessagesEntry,
  PublicUserStats,
  UserStats,
} from "./types"

import { query, seg } from "./query"

const API = process.env.NEXT_PUBLIC_API_URL ?? "/api/proxy"

/** Erreur HTTP de web-api : `status` pour réagir (401, 403, 429…), `message` pour l'afficher. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message)
    this.name = "ApiError"
  }
}

async function failure(res: Response): Promise<ApiError> {
  const body = (await res.json().catch(() => null)) as { detail?: unknown } | null
  const message = typeof body?.detail === "string" ? body.detail : res.statusText || "Erreur API"
  return new ApiError(res.status, message)
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    credentials: "include",
    ...init,
    headers: { "Content-Type": "application/json", ...init.headers },
  })
  if (!res.ok) throw await failure(res)
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

const send = (method: string, body?: unknown): RequestInit => ({
  method,
  body: body === undefined ? undefined : JSON.stringify(body),
})

export const api = {
  auth: {
    me: () => request<SessionUser>("/auth/me"),
  },
  users: {
    stats: (id: Snowflake) => request<UserStats>(`/users/${seg(id)}/stats`),
    publicStats: (id: Snowflake) => request<PublicUserStats>(`/users/${seg(id)}/public`),
  },
  leaderboard: {
    messages: (limit = 10, page = 1) =>
      request<LbPage<MessagesEntry>>(`/leaderboard/messages${query({ page, limit })}`),
    voice: (limit = 10, page = 1) =>
      request<LbPage<VoiceEntry>>(`/leaderboard/voice${query({ page, limit })}`),
  },
  articles: {
    list: (page = 1, limit = 12, tag?: string) =>
      request<ArticleList>(`/articles${query({ page, limit, tag })}`),
    get: (slug: string) => request<Article>(`/articles/${seg(slug)}`),
    create: (data: ArticleCreateInput) => request<Article>("/articles", send("POST", data)),
    update: (id: number, data: Partial<ArticleCreateInput>) =>
      request<Article>(`/articles/${seg(id)}`, send("PUT", data)),
    delete: (id: number) => request<void>(`/articles/${seg(id)}`, send("DELETE")),
  },
  tags: {
    list: () => request<{ tags: Tag[] }>("/tags"),
    create: (data: TagInput) => request<Tag>("/tags", send("POST", data)),
    update: (id: number, data: Partial<TagInput>) => request<Tag>(`/tags/${seg(id)}`, send("PUT", data)),
    delete: (id: number) => request<void>(`/tags/${seg(id)}`, send("DELETE")),
  },
  media: {
    upload: async (file: File) => {
      const form = new FormData()
      form.append("file", file)
      const res = await fetch(`${API}/media/upload`, { method: "POST", credentials: "include", body: form })
      if (!res.ok) throw await failure(res)
      return (await res.json()) as { url: string; filename: string }
    },
  },
  admin: {
    stats: () => request<AdminStats>("/admin/stats"),
    commands: () => request<{ commands: Record<string, boolean> }>("/admin/commands"),
    toggleCommand: (data: CommandToggle) => request<unknown>("/admin/commands/toggle", send("POST", data)),
    kick: (data: ModerationAction) => request<unknown>("/admin/kick", send("POST", data)),
    ban: (data: ModerationAction) => request<unknown>("/admin/ban", send("POST", data)),
    timeout: (data: ModerationAction) => request<unknown>("/admin/timeout", send("POST", data)),
    warn: (data: ModerationAction) => request<unknown>("/admin/warns", send("POST", data)),
    allWarns: () => request<{ warns: AdminWarn[] }>("/admin/warns"),
    getWarns: (userId: Snowflake) => request<{ warns: Warn[] }>(`/admin/warns/${seg(userId)}`),
    deleteWarn: (warnId: number) => request<{ success: boolean }>(`/admin/warns/${seg(warnId)}`, send("DELETE")),
    logs: (page = 1, actionTypes?: string[]) =>
      request<AdminLogPage>(`/admin/logs${query({ page, action_type: actionTypes?.join(",") })}`),
    searchUsers: (q: string) => request<{ users: UserSearchResult[] }>(`/admin/users/search${query({ q })}`),
    settings: () => request<SettingsResponse>("/admin/settings"),
    questTemplates: () => request<{ templates: QuestTemplate[] }>("/admin/quest-templates"),
    createQuestTemplate: (data: QuestTemplateInput) =>
      request<QuestTemplate>("/admin/quest-templates", send("POST", data)),
    updateQuestTemplate: (id: number, data: QuestTemplateInput) =>
      request<QuestTemplate>(`/admin/quest-templates/${seg(id)}`, send("PUT", data)),
    deleteQuestTemplate: (id: number) => request<void>(`/admin/quest-templates/${seg(id)}`, send("DELETE")),
    createGame: (data: GameInput & { key: string }) => request<{ ok: boolean; key: string }>("/admin/games", send("POST", data)),
    updateGame: (key: string, data: Partial<GameInput>) => request<Ok>(`/admin/games/${seg(key)}`, send("PUT", data)),
    deactivateGame: (key: string) => request<Ok>(`/admin/games/${seg(key)}`, send("DELETE")),
    updateGrade: (slug: string, data: GradeInput) => request<Ok>(`/admin/grades/${seg(slug)}`, send("PUT", data)),
    updatePage: (slug: string, data: PageInput) =>
      request<Ok>(`/admin/pages/${seg(slug)}`, send("PUT", data)),
    updateStaffProfile: (userId: Snowflake, data: StaffProfileInput) =>
      request<Ok>(`/admin/staff/${seg(userId)}`, send("PUT", data)),
    setGalleryHidden: (id: number, hidden: boolean) =>
      request<{ id: number; hidden: boolean }>(`/admin/gallery/${seg(id)}`, send("PATCH", { hidden })),
    deleteGalleryItem: (id: number) => request<void>(`/admin/gallery/${seg(id)}`, send("DELETE")),
  },
  staff: {
    updateMyProfile: (data: StaffProfileInput) => request<Ok>("/staff/me", send("PUT", data)),
  },
  tickets: {
    list: (status: "all" | "open" | "closed" = "all", page = 1, limit = 20) =>
      request<TicketList>(`/tickets${query({ status, page, limit })}`),
  },
  xp: {
    leaderboard: (period: XpPeriod = "all", limit?: number) =>
      request<{ leaderboard: XpEntry[] }>(`/xp/leaderboard${query({ period, limit })}`),
    get: (userId: Snowflake) => request<XpData>(`/xp/${seg(userId)}`),
  },
  notifications: {
    list: () => request<{ notifications: Notification[] }>("/notifications"),
    markRead: (id: number) => request<{ success: boolean }>(`/notifications/${seg(id)}/read`, send("POST")),
    markAllRead: () => request<{ success: boolean }>("/notifications/read-all", send("POST")),
  },
  endorsements: {
    get: (userId: Snowflake) => request<Endorsements>(`/endorsements/${seg(userId)}`),
    endorse: (data: { target_user_id: Snowflake; skill: string }) =>
      request<{ success: boolean }>("/endorsements", send("POST", data)),
    leaderboard: (limit?: number) =>
      request<{ leaderboard: ReputationEntry[] }>(`/endorsements${query({ limit })}`),
  },
  activity: {
    heatmap: (userId: Snowflake, days?: number) =>
      request<{ heatmap: ActivityDay[] }>(`/activity/${seg(userId)}/heatmap${query({ days })}`),
    daily: (userId: Snowflake, days?: number) =>
      request<{ daily: DailyActivity[] }>(`/activity/${seg(userId)}/daily${query({ days })}`),
  },
  quests: {
    list: () => request<{ quests: Quest[] }>("/quests"),
    claim: (questId: number) => request<QuestClaim>(`/quests/${seg(questId)}/claim`, send("POST")),
  },
  comments: {
    list: (articleId: number) => request<{ comments: ArticleComment[] }>(`/comments/article/${seg(articleId)}`),
    create: (data: { article_id: number; content: string; parent_id?: number }) =>
      request<ArticleComment>("/comments", send("POST", data)),
    delete: (id: number) => request<void>(`/comments/${seg(id)}`, send("DELETE")),
    vote: (id: number) => request<{ voted: boolean }>(`/comments/${seg(id)}/vote`, send("POST")),
  },
}
