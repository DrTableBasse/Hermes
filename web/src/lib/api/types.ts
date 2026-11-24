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

import type { SitePermission } from "@/lib/permissions"

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
  /** Commande slash du jeu, `null` tant qu'elle n'est pas inscrite (non provisionné ou archivé). */
  command_name?: string | null
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
  /** Droits effectifs, triés (tout le catalogue pour le propriétaire et le rôle admin). */
  permissions: SitePermission[]
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
  global_rank: number
}

/** `/leaderboard/xp` et `/xp/leaderboard` : lignes brutes de `user_xp`. */
export interface XpEntry extends RankedUser {
  total_xp: number
  weekly_xp: number
  current_level: number
}

export type XpPeriod = "all" | "weekly"

export interface MyRanks {
  global_rank: number
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

/** Ligne du journal unique (`GET /admin/audit`). Dates en UTC (ISO 8601 avec décalage). */
export interface AuditEvent {
  id: number
  occurred_at: string
  kind: string
  action: string
  source: string
  actor_id: Snowflake | null
  actor_name: string | null
  target_id: Snowflake | null
  target_name: string | null
  channel_id: Snowflake | null
  channel_name: string | null
  success: boolean
  /** Jamais null : `{}` si vide. */
  details: Record<string, unknown>
}

export interface AuditPage {
  events: AuditEvent[]
  total: number
  page: number
  pages: number
}

/** Actions présentes par type, et salons connus du journal (`GET /admin/audit/facets`). */
export interface AuditFacets {
  kinds: Record<string, string[]>
  channels: { id: Snowflake; name: string }[]
}

/** Filtres du journal ; champs absents ou vides = pas de filtre. `from`/`to` : `YYYY-MM-DD`. */
export interface AuditFilters {
  kind?: string[]
  action?: string[]
  source?: string[]
  channelId?: Snowflake
  actor?: string
  target?: string
  from?: string
  to?: string
  failedOnly?: boolean
  q?: string
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
  emoji?: string
  command_name?: string
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
  /** Rôle qui donne des droits : modifiable par le propriétaire et les admins seulement. */
  admin_only: boolean
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

// ── Administration : lectures propres aux sous-pages ─────────────────────────

/** `GET /admin/commands` : état de chaque commande slash et sa description Discord. */
export interface CommandsResponse {
  commands: Record<string, boolean>
  descriptions?: Record<string, string>
}

export type DiscordChannelType = "text" | "forum" | "voice" | "category"

/** `GET /admin/discord/channels` (salons et catégories du serveur, dans l'ordre Discord). */
export interface DiscordChannel {
  id: Snowflake
  name: string
  type: DiscordChannelType
  /** Catégorie parente ; `null` à la racine ou pour une catégorie. */
  category: string | null
}

/** `GET /admin/discord/roles` (sans @everyone, du plus haut au plus bas). */
export interface DiscordRole {
  id: Snowflake
  name: string
  /** Couleur Discord en entier (0 : pas de couleur). */
  color: number
}

// ── Accès au site par rôle : /admin/access ───────────────────────────────────

export interface AccessRole {
  id: Snowflake
  name: string
  color: number
  /** Position Discord (plus haut = plus grand). */
  position: number
  /** Rôle géré par une intégration (bot) : non attribuable à la main. */
  managed: boolean
  permissions: string[]
  /** Propriétaire, ou rôle strictement sous le rôle le plus haut de l'acteur. */
  editable: boolean
}

/** `GET /admin/access` : rôles par position décroissante, sans @everyone. */
export interface AccessOverview {
  catalog: Array<{ key: string; label: string }>
  roles: AccessRole[]
  actor: { top_position: number; is_owner: boolean; permissions: string[] }
}

/** `PUT /admin/access/{role_id}` : droits enregistrés, dédoublonnés et triés. */
export interface AccessUpdateResult {
  id: Snowflake
  permissions: string[]
}

/** Rôle de `GET /admin/permissions/discord` (même forme dans la réponse du PUT). */
export interface DiscordPermissionRole {
  id: Snowflake
  name: string
  position: number
  managed: boolean
  /** @everyone. */
  is_default: boolean
  /** Drapeaux du catalogue (`PERMISSION_FAMILIES`) accordés au rôle. */
  permissions: string[]
  editable: boolean
  /** Raison rédigée par l'API quand le rôle n'est pas modifiable. */
  refusal: string | null
  /** Drapeaux que l'acteur peut basculer seul sur ce rôle (`[]` si non modifiable). */
  editable_flags: string[]
}

/** `GET /admin/permissions/discord` : rôles du plus haut au plus bas, @everyone compris. */
export interface DiscordPermissionsOverview {
  families: Array<{ family: string; permissions: Array<{ key: string; label: string }> }>
  roles: DiscordPermissionRole[]
  actor: { is_owner: boolean; top_position: number; permissions: string[]; is_admin: boolean }
}

/** `PUT /admin/permissions/discord/{role_id}`. */
export interface DiscordPermissionsUpdateResult {
  changed: boolean
  role: DiscordPermissionRole
}

/** Commande Hermes et sa liste blanche de rôles. */
export interface CommandPermission {
  name: string
  description: string
  /** Réservée aux admins (`@administration_only`) : liste vide = administrateurs seulement. */
  admin_only: boolean
  /** Protégée aussi par une permission Discord native. */
  native_protected: boolean
  /** Liste blanche ; rôle supprimé de Discord : `name: null, deleted: true`. */
  roles: Array<{ id: Snowflake; name: string | null; deleted: boolean }>
  editable: boolean
}

/** `GET /admin/permissions/commands`. */
export interface CommandPermissionsOverview {
  commands: CommandPermission[]
  roles: Array<{ id: Snowflake; name: string; color: number; position: number; assignable: boolean }>
  actor: { is_owner: boolean; top_position: number; is_admin: boolean }
}

/** `PUT /admin/permissions/commands/{name}` ; `reload_failed` : enregistré, bot pas encore à jour. */
export interface CommandPermissionsUpdateResult {
  command: string
  role_ids: Snowflake[]
  changed: boolean
  reload_failed: boolean
}

/** `PUT /admin/settings/{key}` ; `value` vide : réglage effacé, le défaut s'applique. */
export interface SettingPutResult {
  key: string
  value: string
  bot_reloaded: boolean
}

/** `POST /admin/settings/{key}/create-channel` : le salon réglé (créé s'il manquait). */
export interface CreatedChannel {
  id: Snowflake
  name: string
}

/** `GET /admin/games` : tous les jeux, désactivés compris, avec leurs champs éditables. */
export interface AdminGame {
  key: string
  name: string
  color: string
  image: string | null
  tagline: string | null
  discord_role_id: Snowflake | null
  forum_channel_id: Snowflake | null
  position: number
  /** Affiché sur le site public. */
  active: boolean
  emoji: string | null
  command_name: string | null
  lfg_cooldown: number
  /** Rôle, forum et commande créés ou rattachés par le bot. */
  provisioned: boolean
  /** Désactivé côté Discord : commande retirée, forum archivé. */
  archived: boolean
  /** État Discord d'après le bot ; `null` : bot muet ou jeu pas encore relu. */
  status: GameDiscordStatus | null
}

export type GameDiscordStatus = {
  role: "ok" | "missing"
  forum: "ok" | "missing"
  command: "ok" | "missing" | "none"
}

/** `GET /admin/games`. */
export interface AdminGamesResponse {
  bot_reachable: boolean
  games: AdminGame[]
}

/** `POST /admin/games/{key}/provision` : `created` vide = rôle et forum réutilisés. */
/** Surcharge de permissions d'un forum (noms discord.py) : `GET /admin/games/resync-permissions`. */
export interface ForumOverwrite {
  allow: string[]
  deny: string[]
}

/** Aperçu en lecture seule de la réécriture d'un forum de jeu : surcharges retirées, modifiées, ajoutées. */
export interface ForumResyncPreview {
  key: string
  game: string
  forum_id: Snowflake
  forum: string
  changes: Array<{
    target: string
    kind: "role" | "member"
    change: "removed" | "modified" | "added"
    before: ForumOverwrite | null
    after: ForumOverwrite | null
  }>
}

/** Forum resté en échec lors d'une réécriture partielle. */
export interface ForumResyncFailure {
  key: string
  forum: string
  error: string
}

export interface GameProvisionResult {
  role_id: Snowflake
  forum_id: Snowflake
  command: string | null
  created: Array<"role" | "forum">
  status: GameDiscordStatus | null
}

/** `GET /admin/gallery` : élément de galerie avec son état de modération. */
export interface AdminGalleryItem extends GalleryItem {
  hidden: boolean
}

/** `GET /admin/quests/active` : quête de la semaine et sa participation. */
export interface ActiveQuest {
  id: number
  title: string
  description: string | null
  quest_type: string
  target_value: number
  xp_reward: number
  icon: string
  week_start: string
  week_end: string
  participant_count: number
  completed_count: number
}

export interface QuestDeployResult {
  deployed: number
  week_start: string
  week_end: string
}

/** `GET /admin/analytics`. */
export interface AnalyticsData {
  actions_14d: Array<{ date: string; label: string; warn: number; kick: number; ban: number; timeout: number }>
  level_distribution: Array<{ level_range: string; count: number }>
  quest_completion: Array<{ title: string; participants: number; completed: number; rate: number }>
  top_xp_weekly: Array<{ username: string; weekly_xp: number }>
  summary: { active_members: number; total_messages: number; warns_30d: number; quests_done_7d: number }
}

// ── Rôles et règles automatiques : /admin/roles, /admin/role-rules, /admin/jobs ─

/** Rôle du serveur vu par la gestion des rôles (`GET /admin/roles`). */
export interface ManagedRole {
  id: Snowflake
  name: string
  color: number
  position: number
  /** Géré par une intégration : jamais modifiable ni attribuable. */
  managed: boolean
  /** Porteurs du rôle (bots compris). */
  members: number
  /** Strictement sous le rôle le plus haut du bot. */
  below_bot: boolean
  /** Non géré par une intégration, sous le bot, sous l'acteur (ou acteur propriétaire). */
  editable: boolean
}

/** Rôle porté par un membre (`GET /admin/members/{id}/roles`), du plus haut au plus bas. */
export interface MemberRole {
  id: Snowflake
  name: string
  color: number
  position: number
  managed: boolean
  /** L'acteur peut le retirer (`members.roles`, sous lui et sous le bot, non géré par une intégration). */
  editable: boolean
}

export interface RolesOverview {
  roles: ManagedRole[]
  actor: { top_position: number; is_owner: boolean; permissions: string[] }
}

export interface RoleInput {
  name: string
  color: number
}

/** Lot : exactement une source, `confirm_count` = nombre affiché. */
export type BulkRolesInput = { action: "add" | "remove"; confirm_count: number } & (
  | { user_ids: Snowflake[] }
  | { from_role_id: Snowflake }
)

/** État d'un travail du bot ; `added`… présents pour l'application d'une règle. */
export interface RoleJob {
  state: "running" | "done" | "interrupted" | "failed"
  done: number
  total: number
  errors: number
  added?: number
  removed?: number
  skipped?: number
  missing_role?: boolean
}

export type RoleRuleCondition =
  | "voice_hours"
  | "messages"
  | "level"
  | "grade"
  | "achievement"
  | "streak_days"
  | "bumps"
  | "invites"

export interface RoleRule {
  id: number
  condition_type: RoleRuleCondition
  condition_value: string
  role_id: Snowflake | null
  /** Ancien rôle mémorisé au dernier changement de rôle (seul retirable par « apply »). */
  previous_role_id: Snowflake | null
  create_role_name: string | null
  create_role_color: number | null
  remove_when_lost: boolean
  exclusive_group: string | null
  active: boolean
  /** Faux : mode aperçu (seule l'évaluation à l'évènement agit). */
  reconcile: boolean
  role_name: string | null
  /** Le rôle cible n'existe plus sur le serveur. */
  missing_role: boolean
  achievement_name?: string | null
}

export interface RoleRuleInput {
  condition_type: RoleRuleCondition
  condition_value: string
  role_id?: Snowflake | null
  create_role_name?: string | null
  create_role_color?: number | null
  remove_when_lost?: boolean
  exclusive_group?: string | null
  active?: boolean
}

export interface RoleRuleWriteResult {
  rule: RoleRule
  /** Faux : Hermes n'a pas rechargé ses règles (effet à son redémarrage). */
  reloaded: boolean
}

export interface RoleRuleUpdateResult extends RoleRuleWriteResult {
  /** Renseigné quand le rôle de la règle a changé. */
  previous_role: { id: Snowflake; name: string; members: number } | null
}

export interface RoleRulePreview {
  gain: Array<{ id: Snowflake; name: string }>
  lose: Array<{ id: Snowflake; name: string }>
  missing_role: boolean
}

export interface RoleRuleApplyInput {
  confirm: true
  remove_previous_role_id?: Snowflake
  confirm_previous_members?: number
}

// ── Salons et modèles d'accès : /admin/channels (étape 5) ───────────────────

export type ChannelKind = "text" | "voice" | "forum" | "announcement" | "category"
export type ChannelTemplateName = "public" | "role_required" | "announcements" | "staff"

/** Salon de l'arbre (ordre Discord : salons sans catégorie, puis chaque catégorie suivie des siens). */
export interface ManagedChannel {
  id: Snowflake
  name: string
  type: ChannelKind
  position: number
  parent_id: Snowflake | null
  /** Nombre de surcharges de permissions du salon. */
  overwrites: number
  /** Dernier modèle appliqué depuis le site (`null` : aucun). */
  template: { template: ChannelTemplateName; roles: Snowflake[]; applied_by: string | null; applied_at: string | null } | null
  /** L'acteur voit le salon dans Discord (propriétaire : toujours). */
  visible_to_actor: boolean
}

export interface ChannelRole {
  id: Snowflake
  name: string
  color: number
  position: number
  managed: boolean
  /** Utilisable comme rôle d'un modèle : strictement sous l'acteur (ou acteur propriétaire). */
  assignable: boolean
}

export interface ChannelsOverview {
  channels: ManagedChannel[]
  /** Modèles proposés (« staff » : admins seulement). */
  templates: ChannelTemplateName[]
  roles: ChannelRole[]
  actor: { top_position: number; is_owner: boolean; permissions: string[]; is_admin: boolean }
  /** Admin : salons « Staff » appliqués avec d'autres rôles que les `staff_roles` actuels. */
  staff_resync: { pending: number; channel_ids: Snowflake[]; staff_roles_set: boolean } | null
}

export interface ChannelInput {
  name: string
  type: ChannelKind
  parent_id?: Snowflake
}

/** `parent_id: null` : sortir de la catégorie ; absent : inchangé. */
export interface ChannelUpdateInput {
  name?: string
  parent_id?: Snowflake | null
  position?: number
}

export type OverwriteBits = { allow: string[]; deny: string[] }

export interface OverwriteChange {
  target_id: Snowflake
  target_type: "role" | "member"
  target_name: string
  action: "add" | "update" | "remove"
  before: OverwriteBits | null
  after: OverwriteBits | null
}

export interface TemplatePreviewResult {
  channels: Array<{ id: Snowflake; name: string; type: ChannelKind; changes: OverwriteChange[] }>
  /** Nombre de salons concernés (catégorie + salons si synchronisée). */
  count: number
  token: string
}

export interface TemplateInput {
  template: ChannelTemplateName
  roles: Snowflake[]
  sync_children: boolean
}

export interface TemplateApplyResult {
  applied: number
  failed: Array<{ id: Snowflake; name: string; error: string }>
  /** Salons modifiés sur Discord dont la mémorisation a échoué (resynchronisation Staff impossible). */
  memo_failed: Snowflake[]
}
