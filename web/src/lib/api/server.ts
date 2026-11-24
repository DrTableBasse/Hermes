import "server-only"

import type {
  AccessOverview,
  AchievementCatalog,
  ActiveQuest,
  AdminGalleryItem,
  AdminGamesResponse,
  AdminStats,
  AnalyticsData,
  CommandsResponse,
  DiscordChannel,
  DiscordRole,
  QuestTemplate,
  RoleRule,
  RolesOverview,
  SettingsResponse,
  AchievementEntry,
  AchievementWithStatus,
  ActivityDay,
  Article,
  ArticleList,
  ArticleListParams,
  BumpEntry,
  EventsResponse,
  GalleryResponse,
  GamesResponse,
  GlobalEntry,
  Grade,
  GradesResponse,
  HermesStatus,
  InviteEntry,
  LbPage,
  LevelEntry,
  LiveFeed,
  LiveState,
  MessagesEntry,
  MyRanks,
  PublicSettings,
  PublicUserStats,
  Quest,
  SessionUser,
  SitePage,
  StaffResponse,
  StreakEntry,
  Tag,
  TicketList,
  TicketStatus,
  UserStats,
  VoiceEntry,
  XpData,
  XpEntry,
} from "./types"
import { headers } from "next/headers"
import { unstable_rethrow } from "next/navigation"
import { refreshRolesInBackground } from "@/lib/role-refresh"
import { clientIp, sessionCookie, SSR_TIMEOUT_MS } from "./forward"
import { query, seg } from "./query"

export interface ApiOptions {
  /** Jeton de session BetterAuth, transmis en cookie. */
  token?: string
  /** Durée de cache en secondes (`next.revalidate`) ; sans valeur, aucun cache. */
  revalidate?: number
}

function baseUrl(): string {
  return process.env.WEB_API_INTERNAL_URL ?? "http://web-api:8000"
}

/** IP du visiteur de la requête en cours ; `null` hors requête (prérendu, script). */
async function visitorIp(): Promise<string | null> {
  try {
    return clientIp(await headers())
  } catch (e) {
    unstable_rethrow(e) // signal de rendu dynamique de Next : à laisser passer
    return null
  }
}

async function request(path: string, opts: ApiOptions): Promise<Response> {
  const hdrs: Record<string, string> = {}
  if (opts.token) {
    hdrs.Cookie = sessionCookie(opts.token)
    refreshRolesInBackground(opts.token)
  }
  const init: RequestInit = { headers: hdrs, signal: AbortSignal.timeout(SSR_TIMEOUT_MS) }
  // Une réponse obtenue avec une session est personnelle : jamais dans le cache de données Next,
  // même si l'appelant a demandé un revalidate.
  if (opts.token || opts.revalidate === undefined) {
    init.cache = "no-store"
    // Lecture propre au visiteur : comptée sous son IP par le limiteur de web-api, pas sous celle
    // du conteneur (un seul compteur pour tout le site). Les lectures mises en cache n'en portent
    // pas : l'en-tête entrerait dans la clé du cache de données Next, une entrée par visiteur ;
    // elles n'atteignent web-api qu'une fois par période de revalidation.
    const ip = await visitorIp()
    if (ip) hdrs["X-Client-IP"] = ip
  } else init.next = { revalidate: opts.revalidate }
  const res = await fetch(`${baseUrl()}${path}`, init)
  if (!res.ok) throw new Error(`${res.status} ${path}`)
  return res
}

/** GET typé ; lève une erreur contenant le statut HTTP (et sur un 204, sans corps à décoder). */
export async function apiGet<T>(path: string, opts: ApiOptions = {}): Promise<T> {
  const res = await request(path, opts)
  if (res.status === 204) throw new Error(`204 ${path}`)
  return (await res.json()) as T
}

/**
 * GET tolérant, pour les sections « directes » : 204, erreur HTTP, erreur réseau
 * ou corps illisible → `null`. La section affiche alors son état dégradé.
 */
export async function apiGetOrNull<T>(path: string, opts: ApiOptions = {}): Promise<T | null> {
  try {
    const res = await request(path, opts)
    if (res.status === 204) return null
    return (await res.json()) as T
  } catch {
    return null
  }
}

// ── Sections publiques de l'accueil et des pages vitrines ───────────────────

export const getLive = () => apiGetOrNull<LiveState>("/live", { revalidate: 30 })

export const getLiveFeed = () => apiGetOrNull<LiveFeed>("/live/feed", { revalidate: 60 })

export const getEvents = () => apiGetOrNull<EventsResponse>("/events", { revalidate: 60 })

export const getHermesStatus = () => apiGetOrNull<HermesStatus>("/hermes/status", { revalidate: 30 })

export const getGallery = (limit = 30) =>
  apiGetOrNull<GalleryResponse>(`/gallery${query({ limit })}`, { revalidate: 60 })

export const getGalleryHighlights = () =>
  apiGetOrNull<GalleryResponse>("/gallery/highlights", { revalidate: 60 })

/**
 * État-major. Avec `token` (formulaire de `/profil`), lecture fraîche hors cache Next : le membre doit
 * retrouver la phrase qu'il vient d'enregistrer, pas celle d'il y a cinq minutes.
 */
export const getStaff = (token?: string) =>
  apiGetOrNull<StaffResponse>("/staff", token ? { token } : { revalidate: 300 })

export async function getGrades(): Promise<Grade[] | null> {
  const data = await apiGetOrNull<GradesResponse>("/grades", { revalidate: 600 })
  return data ? data.grades : null
}

export const getAchievementCatalog = () =>
  apiGetOrNull<AchievementCatalog>("/achievements", { revalidate: 300 })

export const getGames = () => apiGetOrNull<GamesResponse>("/games", { revalidate: 30 })

export async function getPage(slug: string): Promise<SitePage | null> {
  return apiGetOrNull<SitePage>(`/pages/${seg(slug)}`, { revalidate: 300 })
}

export const getPublicSettings = () =>
  apiGetOrNull<PublicSettings>("/settings/public", { revalidate: 300 })

// ── Articles ─────────────────────────────────────────────────────────────────

export function listArticles(params: ArticleListParams = {}): Promise<ArticleList> {
  return apiGet<ArticleList>(`/articles${query({ ...params })}`)
}

export async function listTags(): Promise<Tag[]> {
  return (await apiGet<{ tags: Tag[] }>("/tags")).tags
}

export async function getArticle(slug: string, token?: string): Promise<Article> {
  return apiGet<Article>(`/articles/${seg(slug)}`, { token })
}

/** Article par identifiant numérique (éditeur) ; brouillon visible de son auteur et des administrateurs. */
export async function getArticleById(id: number, token?: string): Promise<Article> {
  return apiGet<Article>(`/articles/by-id/${seg(id)}`, { token })
}

export async function myArticles(token: string): Promise<Article[]> {
  return (await apiGet<{ articles: Article[] }>("/articles/mine", { token })).articles
}

// ── Utilisateurs ─────────────────────────────────────────────────────────────

export async function getUserStats(userId: string, token: string): Promise<UserStats> {
  return apiGet<UserStats>(`/users/${seg(userId)}/stats`, { token })
}

export async function getUserPublicStats(userId: string): Promise<PublicUserStats> {
  return apiGet<PublicUserStats>(`/users/${seg(userId)}/public`)
}

export async function getUserActivity(userId: string): Promise<ActivityDay[]> {
  return (await apiGet<{ heatmap: ActivityDay[] }>(`/activity/${seg(userId)}/heatmap?days=365`)).heatmap
}

/** Membre de la session (`/auth/me`) ; `null` : session absente, expirée ou API muette. */
export const getSessionUser = (token: string) => apiGetOrNull<SessionUser>("/auth/me", { token })

/** Quêtes actives et avancement du membre (`/quests`, session requise) ; `null` en cas d'échec. */
export async function getWeeklyQuests(token: string): Promise<Quest[] | null> {
  const data = await apiGetOrNull<{ quests: Quest[] }>("/quests", { token })
  return data ? data.quests : null
}

/** Niveau, XP et grade du membre (`/xp/{id}`) ; `null` en cas d'échec. */
export async function getXp(userId: string, token: string): Promise<XpData | null> {
  return apiGetOrNull<XpData>(`/xp/${seg(userId)}`, { token })
}

/** Tickets du membre connecté (`/tickets/mine`) ; `null` : session refusée ou API muette. */
export const getMyTickets = (token: string, status: TicketStatus | "all" = "all", page = 1, limit = 20) =>
  apiGetOrNull<TicketList>(`/tickets/mine${query({ status, page, limit })}`, { token })

/** Historique global des tickets (`/tickets`, administrateurs) ; `null` : accès refusé ou API muette. */
export const getTickets = (token: string, status: TicketStatus | "all" = "all", page = 1, limit = 20) =>
  apiGetOrNull<TicketList>(`/tickets${query({ status, page, limit })}`, { token })

export async function getUserAchievementsAll(userId: string): Promise<AchievementWithStatus[]> {
  return (await apiGet<{ achievements: AchievementWithStatus[] }>(`/users/${seg(userId)}/achievements`))
    .achievements
}

// ── Classements ──────────────────────────────────────────────────────────────

function leaderboardPage<T>(kind: string, page: number, limit: number, search?: string) {
  return apiGet<LbPage<T>>(`/leaderboard/${kind}${query({ page, limit, search })}`)
}

export const leaderboardVoice = (page = 1, limit = 5, search?: string) =>
  leaderboardPage<VoiceEntry>("voice", page, limit, search)

export const leaderboardMessages = (page = 1, limit = 5, search?: string) =>
  leaderboardPage<MessagesEntry>("messages", page, limit, search)

export const leaderboardAchievements = (page = 1, limit = 5, search?: string) =>
  leaderboardPage<AchievementEntry>("achievements", page, limit, search)

export const leaderboardBumps = (page = 1, limit = 5, search?: string) =>
  leaderboardPage<BumpEntry>("bumps", page, limit, search)

export const leaderboardInvites = (page = 1, limit = 5, search?: string) =>
  leaderboardPage<InviteEntry>("invites", page, limit, search)

export const leaderboardLevels = (page = 1, limit = 5, search?: string) =>
  leaderboardPage<LevelEntry>("levels", page, limit, search)

export const leaderboardStreaks = (page = 1, limit = 5, search?: string) =>
  leaderboardPage<StreakEntry>("streaks", page, limit, search)

export function myRanks(token: string): Promise<MyRanks> {
  return apiGet<MyRanks>("/leaderboard/me", { token })
}

/** Classement global : 1 pt par minute de vocal + 1 pt par message + 200 pts par succès. */
export const leaderboardGlobal = (page = 1, limit = 5, search?: string) =>
  leaderboardPage<GlobalEntry>("global", page, limit, search)

export async function listVoiceLeaderboard(limit = 5): Promise<VoiceEntry[]> {
  return (await apiGet<LbPage<VoiceEntry>>(`/leaderboard/voice${query({ limit })}`)).leaderboard
}

export async function listMessagesLeaderboard(limit = 20): Promise<MessagesEntry[]> {
  return (await apiGet<LbPage<MessagesEntry>>(`/leaderboard/messages${query({ limit })}`)).leaderboard
}

export function searchUserByUsername(queryText: string): Promise<LbPage<MessagesEntry>> {
  return apiGet<LbPage<MessagesEntry>>(`/leaderboard/messages${query({ search: queryText, limit: 1 })}`)
}

/** `/xp/leaderboard` renvoie `{ leaderboard }` sans pagination (≠ `/leaderboard/xp`). */
export async function leaderboardXpWeekly(limit = 10): Promise<XpEntry[]> {
  return (await apiGet<{ leaderboard: XpEntry[] }>(`/xp/leaderboard${query({ period: "weekly", limit })}`))
    .leaderboard
}

// ── Administration (session admin ; avec un jeton, jamais de cache Next) ─────

export const getAdminStats = (token: string) => apiGetOrNull<AdminStats>("/admin/stats", { token })

export const getAdminCommands = (token: string) => apiGetOrNull<CommandsResponse>("/admin/commands", { token })

export const getAdminSettings = (token: string) => apiGetOrNull<SettingsResponse>("/admin/settings", { token })

/** Liste Discord de l'admin : `"forbidden"` sur un 403 (droit absent), `null` si illisible (bot muet). */
export type DiscordList<T> = T[] | null | "forbidden"

async function discordList<T>(path: string, key: string, token: string): Promise<DiscordList<T>> {
  try {
    const res = await request(path, { token })
    if (res.status === 204) return null
    const data = (await res.json()) as Record<string, T[]>
    return data[key] ?? null
  } catch (e) {
    // `request` lève `Error("<statut> <chemin>")` sur une réponse non 2xx.
    return e instanceof Error && e.message.startsWith("403 ") ? "forbidden" : null
  }
}

/** Salons du serveur. */
export const getDiscordChannels = (token: string) =>
  discordList<DiscordChannel>("/admin/discord/channels", "channels", token)

/** Rôles et droits d'accès au site (`permissions.manage`). */
export const getAdminAccess = (token: string) => apiGetOrNull<AccessOverview>("/admin/access", { token })

/** Rôles du serveur. */
export const getDiscordRoles = (token: string) => discordList<DiscordRole>("/admin/discord/roles", "roles", token)

/** Rôles gérables et rang de l'acteur (`roles.manage` ou `members.roles`). */
export const getAdminRoles = (token: string) => apiGetOrNull<RolesOverview>("/admin/roles", { token })

/** Règles automatiques de rôles (`roles.manage`) ; `null` si illisibles. */
export async function getRoleRules(token: string): Promise<RoleRule[] | null> {
  const data = await apiGetOrNull<{ rules: RoleRule[] }>("/admin/role-rules", { token })
  return data ? data.rules : null
}

export async function getAdminGames(token: string): Promise<AdminGamesResponse | null> {
  return apiGetOrNull<AdminGamesResponse>("/admin/games", { token })
}

export async function getAdminGallery(token: string): Promise<AdminGalleryItem[] | null> {
  const data = await apiGetOrNull<{ items: AdminGalleryItem[] }>("/admin/gallery", { token })
  return data ? data.items : null
}

export async function getQuestTemplates(token: string): Promise<QuestTemplate[] | null> {
  const data = await apiGetOrNull<{ templates: QuestTemplate[] }>("/admin/quest-templates", { token })
  return data ? data.templates : null
}

export async function getActiveQuests(token: string): Promise<ActiveQuest[] | null> {
  const data = await apiGetOrNull<{ quests: ActiveQuest[] }>("/admin/quests/active", { token })
  return data ? data.quests : null
}

export const getAnalytics = (token: string) => apiGetOrNull<AnalyticsData>("/admin/analytics", { token })

/** Page Markdown lue fraîche pour l'éditeur (le texte public est mis en cache cinq minutes). */
export const getPageFresh = (slug: string, token: string) =>
  apiGetOrNull<SitePage>(`/pages/${seg(slug)}`, { token })

/** Grades lus frais pour l'éditeur ; `null` en cas d'échec. */
export async function getGradesFresh(token: string): Promise<Grade[] | null> {
  const data = await apiGetOrNull<GradesResponse>("/grades", { token })
  return data ? data.grades : null
}
