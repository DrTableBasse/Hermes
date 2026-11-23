/** Journal unique : libellés français, détail lisible, filtres ⇄ requête API et URL de la page. */
import type { AuditEvent, AuditFilters } from "./api/types"

export const KIND_LABELS: Record<string, string> = {
  command: "Commande",
  sanction: "Sanction",
  message: "Message",
  voice: "Vocal",
  member: "Membre",
  member_role: "Rôle de membre",
  role: "Rôle",
  channel: "Salon",
  thread: "Fil",
  invite: "Invitation",
  emoji: "Émoji",
  server: "Serveur",
  permission: "Permission",
  setting: "Réglage",
  game: "Jeu",
  site_access: "Accès au site",
  content: "Contenu",
}

export const SOURCE_LABELS: Record<string, string> = {
  site: "Site",
  hermes: "Hermes",
  discord: "Discord",
}

/** Libellé d'une action seule (menu Action) ; une commande (`/nom`) s'affiche telle quelle. */
export const ACTION_LABELS: Record<string, string> = {
  edit: "modifié",
  delete: "supprimé",
  bulk_delete: "suppression en masse",
  join: "arrivée",
  leave: "départ",
  move: "déplacé",
  server_mute: "micro (modération)",
  server_deafen: "casque (modération)",
  self_mute: "micro",
  self_deafen: "casque",
  stream_start: "partage d’écran lancé",
  stream_stop: "partage d’écran arrêté",
  nickname: "pseudo modifié",
  add: "ajouté",
  remove: "retiré",
  create: "créé",
  update: "modifié",
  kick: "expulsion",
  ban: "bannissement",
  unban: "débannissement",
  timeout: "exclusion temporaire",
  untimeout: "fin d’exclusion",
  warn: "avertissement",
  clear: "nettoyage de messages",
  message_delete: "message supprimé",
  message_bulk_delete: "messages supprimés en masse",
  delete_warn: "sanction retirée",
  command_toggle: "commande activée ou coupée",
  quest_template_create: "quête créée",
  quest_template_update: "quête modifiée",
  quest_template_delete: "quête supprimée",
  quest_deploy: "quêtes déployées",
}

export function actionLabel(action: string): string {
  return ACTION_LABELS[action] ?? action
}

/** Vocal à bascule : [activé, désactivé] selon `details.active`. */
const TOGGLES: Record<string, [string, string]> = {
  self_mute: ["micro coupé", "micro réactivé"],
  self_deafen: ["casque coupé", "casque réactivé"],
  server_mute: ["micro coupé par la modération", "micro réactivé par la modération"],
  server_deafen: ["casque coupé par la modération", "casque réactivé par la modération"],
  stream_start: ["partage d’écran lancé", "partage d’écran arrêté"],
  stream_stop: ["partage d’écran lancé", "partage d’écran arrêté"],
}

/** Libellé d'une ligne : tient compte de `details` (micro coupé / réactivé, commande activée / coupée). */
export function eventActionLabel(event: AuditEvent): string {
  const d = event.details
  const toggle = TOGGLES[event.action]
  if (toggle && typeof d.active === "boolean") return d.active ? toggle[0] : toggle[1]
  if (event.action === "command_toggle" && typeof d.command_name === "string" && typeof d.enabled === "boolean") {
    return `/${d.command_name} ${d.enabled ? "activée" : "coupée"}`
  }
  return actionLabel(event.action)
}

const KEY_LABELS: Record<string, string> = {
  reason: "Raison",
  duration_minutes: "Durée (minutes)",
  duration: "Durée",
  content: "Contenu",
  attachments: "Pièces jointes",
  embeds: "Embeds",
  count: "Nombre",
  role: "Rôle",
  from_channel: "Depuis le salon",
  invite_code: "Invitation",
  deleted_by: "Supprimé par",
  overwrite_for: "Permissions de",
  command_name: "Commande",
  enabled: "Activée",
  messages: "Messages en cache",
}

/** Identifiants techniques et valeurs déjà rendues par le libellé d'action. */
const HIDDEN = new Set(["discord_audit_id", "message_id", "role_id", "from_channel_id", "active"])

export type DetailEntry = { label: string; value: string }

const isRecord = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v)

function isEmpty(v: unknown): boolean {
  return v === null || v === undefined || v === "" || (Array.isArray(v) && v.length === 0) || (isRecord(v) && Object.keys(v).length === 0)
}

function text(v: unknown): string {
  if (v === null || v === undefined || v === "") return "—"
  if (typeof v === "boolean") return v ? "oui" : "non"
  if (Array.isArray(v)) return v.length ? v.map(text).join(", ") : "—"
  if (isRecord(v)) return typeof v.name === "string" ? v.name : JSON.stringify(v)
  return String(v)
}

/** Contenu d'un message enregistré (texte, noms des pièces jointes, nombre d'embeds). */
function snapshot(v: unknown): string {
  if (!isRecord(v)) return text(v)
  const parts = [text(v.content)]
  if (Array.isArray(v.attachments) && v.attachments.length) parts.push(`pièces jointes : ${text(v.attachments)}`)
  if (typeof v.embeds === "number" && v.embeds > 0) parts.push(`${v.embeds} embed${v.embeds > 1 ? "s" : ""}`)
  return parts.join(" · ")
}

/** `{champ: {avant, après}}` → « champ : avant → après ». */
function changes(v: unknown): DetailEntry[] {
  if (!isRecord(v)) return []
  return Object.entries(v).map(([field, change]) =>
    isRecord(change) ? { label: field, value: `${text(change.avant)} → ${text(change.après)}` } : { label: field, value: text(change) },
  )
}

/** `details` en paires libellé / valeur lisibles, dans l'ordre enregistré. */
export function detailEntries(event: AuditEvent): DetailEntry[] {
  const out: DetailEntry[] = []
  for (const [key, value] of Object.entries(event.details)) {
    if (HIDDEN.has(key) || isEmpty(value) || (key === "embeds" && value === 0)) continue
    if (key === "avant" || key === "après") {
      out.push({ label: key === "avant" ? "Avant" : "Après", value: snapshot(value) })
    } else if (key === "changes" || key === "permissions") {
      out.push(...changes(value))
    } else if (key === "options" && isRecord(value)) {
      for (const [name, opt] of Object.entries(value)) out.push({ label: `Option « ${name} »`, value: text(opt) })
    } else if (key === "messages" && Array.isArray(value)) {
      const lines = value.map(m => (isRecord(m) ? `${text(m.author_name)} : ${snapshot(m)}` : text(m)))
      out.push({ label: KEY_LABELS.messages, value: lines.join(" / ") })
    } else {
      out.push({ label: KEY_LABELS[key] ?? key, value: text(value) })
    }
  }
  return out
}

const dateTime = new Intl.DateTimeFormat("fr-FR", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  timeZone: "Europe/Paris",
})

/** « 23/11/2026 11:00:00 », heure de Paris. */
export function formatAuditDate(iso: string): string {
  return dateTime.format(new Date(iso))
}

const trimmed = (v: string | undefined) => v?.trim() ?? ""

/**
 * Requête de `GET /admin/audit` (avec `page`) ou de l'export CSV (sans) ; champs vides omis.
 * `failedOnly` → `success=false`.
 */
export function auditQuery(filters: AuditFilters, page?: number): string {
  const qs = new URLSearchParams()
  const put = (key: string, value: string | undefined) => {
    if (trimmed(value)) qs.set(key, trimmed(value))
  }
  put("kind", filters.kind?.join(","))
  put("action", filters.action?.join(","))
  put("source", filters.source?.join(","))
  put("channel_id", filters.channelId)
  put("actor", filters.actor)
  put("target", filters.target)
  put("from", filters.from)
  put("to", filters.to)
  if (filters.failedOnly) qs.set("success", "false")
  put("q", filters.q)
  if (page !== undefined) qs.set("page", String(page))
  return qs.toString()
}

/** Clés de l'URL de la page (partageable) : en français, sauf `action`, `source`, `q` et `page`. */
const URL_KEYS = {
  kind: "type",
  action: "action",
  source: "source",
  channelId: "salon",
  actor: "auteur",
  target: "cible",
  from: "du",
  to: "au",
  q: "q",
} as const

const LIST_KEYS = ["kind", "action", "source"] as const
const TEXT_KEYS = ["channelId", "actor", "target", "from", "to", "q"] as const

export function filtersToParams(filters: AuditFilters, page: number): URLSearchParams {
  const params = new URLSearchParams()
  for (const key of LIST_KEYS) {
    const value = filters[key]?.filter(Boolean).join(",")
    if (value) params.set(URL_KEYS[key], value)
  }
  for (const key of TEXT_KEYS) {
    const value = trimmed(filters[key])
    if (value) params.set(URL_KEYS[key], value)
  }
  if (filters.failedOnly) params.set("echecs", "1")
  if (page > 1) params.set("page", String(page))
  return params
}

/** Lecture de l'URL de la page ; types et sources hors liste fermée ignorés. */
export function filtersFromParams(params: URLSearchParams): { filters: AuditFilters; page: number } {
  const filters: AuditFilters = {}
  const list = (key: (typeof LIST_KEYS)[number], allowed?: Record<string, string>) => {
    const values = (params.get(URL_KEYS[key]) ?? "")
      .split(",")
      .map(v => v.trim())
      .filter(v => v && (!allowed || v in allowed))
    if (values.length) filters[key] = values
  }
  list("kind", KIND_LABELS)
  list("action")
  list("source", SOURCE_LABELS)
  for (const key of TEXT_KEYS) {
    const value = trimmed(params.get(URL_KEYS[key]) ?? undefined)
    if (value) filters[key] = value
  }
  if (params.get("echecs") === "1") filters.failedOnly = true
  const page = Number(params.get("page"))
  return { filters, page: Number.isInteger(page) && page > 1 ? page : 1 }
}

/** Raccourcis : chacun remplace tous les filtres. */
export const SHORTCUTS: { label: string; filters: AuditFilters }[] = [
  { label: "Tout", filters: {} },
  { label: "Sanctions", filters: { kind: ["sanction"] } },
  { label: "Messages", filters: { kind: ["message"] } },
  { label: "Vocal", filters: { kind: ["voice"] } },
  { label: "Membres", filters: { kind: ["member", "member_role"] } },
  { label: "Rôles", filters: { kind: ["role"] } },
  { label: "Salons", filters: { kind: ["channel", "thread"] } },
  { label: "Commandes", filters: { kind: ["command"] } },
  { label: "Site", filters: { source: ["site"] } },
]

/** Deux jeux de filtres équivalents (mêmes paramètres une fois sérialisés). */
export function sameFilters(a: AuditFilters, b: AuditFilters): boolean {
  return auditQuery(a) === auditQuery(b)
}
