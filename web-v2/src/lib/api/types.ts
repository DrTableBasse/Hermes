/**
 * Types des réponses de web-api, relevés sur les routes `web-api/routes/*.py`.
 *
 * - Les identifiants Discord sont toujours des `string` : `SnowflakeJSONResponse`
 *   convertit tout entier > 2^53 en chaîne.
 * - Les identifiants de table (articles, tags, commentaires, quêtes…) restent des `number`.
 * - Une valeur que web-api peut renvoyer à `null` (donnée absente, bot muet) est typée `| null` :
 *   l'interface affiche alors « — », jamais un chiffre inventé.
 * - Dates : chaînes ISO 8601, sauf `Warn.create_time` (timestamp Unix en secondes).
 */

/** Identifiant Discord (snowflake). */
export type Snowflake = string

// ── Grades ───────────────────────────────────────────────────────────────────

/** Forme publique d'un grade, jointe aux niveaux (`public_grade`). */
export interface PublicGrade {
  name: string
  slug: string
  color: string
}

export interface Grade extends PublicGrade {
  level_min: number
}

export interface GradesResponse {
  grades: Grade[]
}

// ── Page d'accueil : /live, /live/feed ───────────────────────────────────────

export interface CurvePoint {
  /** Début de l'heure, ISO 8601 UTC. */
  hour: string
  /** Moyenne des connectés ; `null` quand aucun relevé n'existe pour cette heure. */
  online: number | null
}

export interface LiveState {
  members: number
  online: number
  in_voice: number
  /** URL des avatars des membres en vocal. */
  voice_avatars: string[]
  /** Joueurs par clé de jeu, transmis tels quels par le bot. */
  game_players: Record<string, number>
  /** `true` : le bot est muet, valeurs du dernier relevé en base. */
  stale: boolean
  updated_at: string
  messages_today: number
  /** 24 points, du plus ancien au plus récent. */
  curve_24h: CurvePoint[]
}

export type LiveFeedType = "level_up" | "achievement"

export interface LiveFeedItem {
  type: LiveFeedType
  user_id: Snowflake
  username: string
  avatar: string | null
  label: string
  at: string
}

export interface LiveFeed {
  items: LiveFeedItem[]
}

// ── Events : /events ─────────────────────────────────────────────────────────

export interface EventOrganizer {
  id: Snowflake
  name: string
  avatar: string | null
  grade: PublicGrade
}

/**
 * Event programmé Discord : charge utile du bot (`bot/api.py::_event_payload`)
 * enrichie par web-api (`xp_reward`, `organizer`).
 */
export interface DiscordEvent {
  id: string
  name: string
  description: string | null
  /** Début, ISO 8601. */
  start: string
  end: string | null
  /** Le bot ne relaie que les events à venir ou en cours. */
  status: "scheduled" | "active"
  /** Lieu, ou nom du salon ; `null` sinon. */
  location: string | null
  /** Inscrits ; `null` si Discord ne le fournit pas. */
  user_count: number | null
  creator_id: Snowflake | null
  image: string | null
  url: string
  /** Récompense lue dans la description (`XP: 200`), `null` si absente. */
  xp_reward: number | null
  /** `null` : pas d'organisateur, ou base indisponible. */
  organizer: EventOrganizer | null
}

export interface EventsResponse {
  events: DiscordEvent[]
  /** Présent (`true`) quand la réponse est un dernier état connu. */
  stale?: boolean
}

// ── Statut d'Hermes : /hermes/status ─────────────────────────────────────────

export interface HermesAvailability {
  /** `null` tant que le bot a moins de 30 jours de relevés. */
  percent: number | null
  /** Premier relevé, ISO 8601 ; `null` sans aucun relevé. */
  since: string | null
}

export interface HermesToday {
  /** Aucune table ne journalise l'XP distribuée : toujours `null` pour l'instant. */
  xp_distributed: number | null
  achievements: number | null
  tickets: number | null
  /** Aucune table ne journalise les rappels de bump : toujours `null` pour l'instant. */
  bump_reminders: number | null
}

export interface HermesCurvePoint {
  hour: string
  /** `null` : heure sans relevé. */
  messages: number | null
}

export interface HermesStatus {
  online: boolean
  /** `null` quand le bot est hors ligne ou muet. */
  latency_ms: number | null
  availability: HermesAvailability
  commands_served: number | null
  today: HermesToday
  daily_curve: HermesCurvePoint[]
  /** Présent (`true`) quand une requête a échoué : valeurs de repli. */
  stale?: boolean
}

// ── Galerie : /gallery, /gallery/highlights ──────────────────────────────────

export type GalleryKind = "image" | "clip"

export interface GalleryAuthor {
  id: Snowflake
  name: string
  avatar: string | null
}

export interface GalleryItem {
  id: number
  kind: GalleryKind
  /** Image : chemin `/media/gallery/…` ; clip : URL du clip. */
  url: string | null
  /** Fournisseur du clip ; `null` pour une image. */
  provider: string | null
  caption: string | null
  author: GalleryAuthor
  created_at: string | null
}

export interface GalleryResponse {
  items: GalleryItem[]
}

// ── État-major : /staff ──────────────────────────────────────────────────────

export interface StaffMember {
  id: Snowflake
  name: string
  avatar: string | null
  role: string | null
  /** `null` quand la base est indisponible. */
  grade: PublicGrade | null
  /** `null` quand la base est indisponible. */
  level: number | null
  motto: string | null
  /** Clés de jeux actifs. */
  games: string[]
}

export interface StaffResponse {
  staff: StaffMember[]
  /** Présent (`true`) quand la liste est dégradée ou périmée. */
  stale?: boolean
}

// ── Contenus : /games, /pages/{slug}, /settings/public ───────────────────────

export interface Game {
  key: string
  name: string
  color: string
  image: string | null
  /** Accroche saisie dans l'admin (120 caractères au plus) ; `null` : texte générique. */
  tagline: string | null
  /** `null` : bot muet ou compteur invalide. */
  players: number | null
  forum_url: string | null
}

export interface GamesResponse {
  games: Game[]
  /** Présent (`true`) quand la base est illisible. */
  stale?: boolean
}

export interface SitePage {
  slug: string
  title: string
  body_md: string
  updated_at: string | null
}

export interface PublicSettings {
  invite_url: string | null
  ticket_panel_url: string | null
}

// ── Utilisateur connecté : /auth/me ──────────────────────────────────────────

export interface SessionUser {
  user_id: Snowflake
  is_admin: boolean
  is_redacteur: boolean
}

// ── Articles et tags ─────────────────────────────────────────────────────────

export interface Tag {
  id: number
  name: string
  slug: string
  color: string
}

export interface TagInput {
  name: string
  color?: string
}

export interface ArticleAuthor {
  user_id: Snowflake
  username: string
  discord_avatar: string | null
}

export interface Article {
  id: number
  author_id: Snowflake
  title: string
  slug: string
  content: string
  cover_image_url: string | null
  published: boolean
  created_at: string
  updated_at: string
  tags: Tag[]
  /** `null` : l'auteur a quitté la base. */
  author: ArticleAuthor | null
}

export interface ArticleList {
  articles: Article[]
  total: number
  page: number
  limit: number
}

export interface ArticleCreateInput {
  title: string
  content: string
  cover_image_url?: string | null
  published: boolean
  tag_ids: number[]
}

export interface ArticleListParams {
  page?: number
  limit?: number
  tag?: string
  search?: string
}

// ── Classements : /leaderboard/* et /xp/* ────────────────────────────────────

export interface LbPage<T> {
  leaderboard: T[]
  total: number
  page: number
  limit: number
}

interface RankedUser {
  user_id: Snowflake
  username: string
  discord_avatar: string | null
}

export interface VoiceEntry extends RankedUser {
  total_seconds: number
  formatted: string
  global_rank: number
}

export interface MessagesEntry extends RankedUser {
  total_messages: number
  global_rank: number
}

export interface AchievementEntry extends RankedUser {
  achievement_count: number
  global_rank: number
}

export interface BumpEntry extends RankedUser {
  bump_count: number
  global_rank: number
}

export interface InviteEntry extends RankedUser {
  invite_count: number
  global_rank: number
}

export interface LevelEntry extends RankedUser {
  current_level: number
  total_xp: number
  global_rank: number
  grade: PublicGrade
}

export interface StreakEntry extends RankedUser {
  current_streak: number
  max_streak: number
  xp_multiplier: number
  global_rank: number
}

export interface GlobalEntry extends RankedUser {
  voice_formatted: string
  total_messages: number
  achievement_count: number
  global_score: number
}

/** `/leaderboard/xp` et `/xp/leaderboard` : lignes brutes de `user_xp`. */
export interface XpEntry extends RankedUser {
  total_xp: number
  weekly_xp: number
  current_level: number
}

export type XpPeriod = "all" | "weekly"

export interface MyRanks {
  voice_rank: number
  messages_rank: number
  achievements_rank: number
  bumps_rank: number
  invites_rank: number
  level_rank: number
  streak_rank: number
}

/** `/xp/{user_id}` : ligne `user_xp` (ou zéros) et grade. */
export interface XpData {
  user_id: Snowflake
  total_xp: number
  weekly_xp: number
  current_level: number
  grade: PublicGrade
  [key: string]: unknown
}

// ── Utilisateurs : /users/* ──────────────────────────────────────────────────

export interface Achievement {
  id: number
  name: string
  description: string
  icon: string
  points: number
  unlocked_at: string | null
}

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

/** Ligne du catalogue public `/achievements`. */
export interface CatalogAchievement {
  id: number
  name: string
  description: string | null
  icon: string | null
  points: number
  condition_type: string
  /** Membres actifs (`is_member`) qui l'ont débloqué. */
  unlocked_count: number
}

export interface AchievementCatalog {
  achievements: CatalogAchievement[]
  /** Membres actifs : dénominateur de la rareté. */
  members_total: number
  /** Présent (`true`) quand la base est illisible : liste vide. */
  stale?: boolean
}

/** `/users/{id}/stats` (connecté). */
export interface UserStats {
  user: {
    user_id: Snowflake
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
    max_streak: number
    xp_multiplier: number
    bump_count: number
    bump_rank: number
    msg_current_streak: number
    msg_max_streak: number
  }
  achievements: Achievement[]
}

/** `/users/{id}/public`. */
export interface PublicUserStats {
  user_id: Snowflake
  username: string
  nickname: string | null
  discord_avatar: string | null
  stats: {
    total_messages: number
    voice_seconds: number
    voice_formatted: string
    total_xp: number
    current_level: number
    grade: PublicGrade
    achievement_count: number
    current_streak: number
    bump_count: number
  }
  achievements: Achievement[]
}

// ── Activité, quêtes, notifications, réputation, commentaires ────────────────

export interface ActivityDay {
  date: string
  count: number
}

export interface DailyActivity {
  date: string
  messages: number
}

export type QuestStatus = "active" | "completed" | "claimed"

export interface Quest {
  id: number
  title: string
  description: string | null
  quest_type: string
  target_value: number
  xp_reward: number
  icon: string | null
  current_progress: number
  status: QuestStatus
  week_start: string
  week_end: string
  is_active: boolean
  [key: string]: unknown
}

export interface QuestClaim {
  success: boolean
  xp_reward: number
}

export interface Notification {
  id: number
  user_id: Snowflake
  type: string
  title: string
  body: string | null
  related_id: number | null
  is_read: boolean
  created_at: string
}

export interface EndorsementSkill {
  skill: string
  count: number
}

export interface Endorsements {
  skills: EndorsementSkill[]
  total: number
}

export interface ReputationEntry extends RankedUser {
  total_endorsements: number
}

export interface ArticleComment {
  id: number
  article_id: number
  user_id: Snowflake
  content: string
  parent_id: number | null
  vote_count: number
  created_at: string
  username: string
  discord_avatar: string | null
}

// ── Tickets (admin) ──────────────────────────────────────────────────────────

export type TicketStatus = "open" | "closed"

export interface TicketSummary {
  id: number
  ticket_number: number
  user_id: Snowflake
  username: string
  subject: string | null
  status: TicketStatus
  created_at: string | null
  closed_at: string | null
  has_transcript: boolean
}

export interface TicketList {
  tickets: TicketSummary[]
  total: number
  page: number
  limit: number
}

// ── Administration ───────────────────────────────────────────────────────────

export interface AdminStats {
  members: number
  total_messages: number
  total_warns: number
  total_articles: number
}

export interface CommandToggle {
  command_name: string
  enabled: boolean
}

/** Corps des actions de modération ; `user_id` est un identifiant Discord (chaîne). */
export interface ModerationAction {
  user_id: Snowflake
  reason?: string
  /** Minutes, pour `timeout` (60 par défaut côté API). */
  duration?: number
}

export interface Warn {
  id: number
  user_id: Snowflake
  reason: string
  /** Timestamp Unix, en secondes. */
  create_time: number
  moderator_id: Snowflake
  moderator_username: string | null
}

export interface AdminWarn extends Warn {
  username: string
  discord_avatar: string | null
}

export interface AdminLog {
  id: number
  action_type: string
  actor_id: Snowflake | null
  actor_name: string | null
  target_id: Snowflake | null
  target_name: string | null
  details: Record<string, unknown>
  created_at: string
}

export interface AdminLogPage {
  logs: AdminLog[]
  total: number
  page: number
  pages: number
}

export interface UserSearchResult {
  user_id: Snowflake
  username: string
  discord_avatar: string | null
}

export interface QuestTemplate {
  id: number
  title: string
  description: string | null
  quest_type: string
  target_value: number
  xp_reward: number
  icon: string
  is_enabled: boolean
  [key: string]: unknown
}

export interface QuestTemplateInput {
  title: string
  description?: string | null
  quest_type: string
  target_value: number
  xp_reward?: number
  icon?: string
  is_enabled?: boolean
}

export interface GameInput {
  name: string
  color: string
  image?: string | null
  tagline?: string | null
  discord_role_id?: Snowflake | null
  forum_channel_id?: Snowflake | null
  position?: number
  active?: boolean
}

export interface StaffProfileInput {
  motto: string | null
  games: string[]
}

export interface GradeInput {
  name: string
  color: string
  level_min: number
}

export interface PageInput {
  title: string
  body_md: string
}

export interface SettingItem {
  key: string
  label: string
  kind: string
  value: string
  can_create: boolean
  resolved: { id: string; name: string | null; exists: boolean | null } | null
}

export interface SettingGroup {
  name: string
  items: SettingItem[]
}

export interface SettingsResponse {
  groups: SettingGroup[]
}

export interface Ok {
  ok: boolean
}
