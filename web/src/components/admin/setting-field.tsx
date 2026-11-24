"use client"

import { useId, useState, type FormEvent } from "react"
import { Button } from "@/components/ui/button"
import { Chip } from "@/components/ui/chip"
import { api } from "@/lib/api/client"
import type { DiscordChannel, DiscordRole, SettingItem } from "@/lib/api/types"
import { cn } from "@/lib/cn"
import { adminErrorText, FIELD, type Feedback } from "./form"
import { ForumsResync } from "./forums-resync"
import { isIdKind, isKeySetting, ROLE_LIST_KEYS, splitIds } from "./key-settings"
import { RoleChecklist } from "./role-checklist"

type Props = {
  item: SettingItem
  /** `null` : liste indisponible (bot muet) ; le champ devient une saisie d'identifiant. */
  channels: DiscordChannel[] | null
  roles: DiscordRole[] | null
  onChannelCreated: (channel: DiscordChannel) => void
  /** Réglage réservé aux admins (web-api répondrait 403) : valeur affichée, aucune saisie. */
  readOnly?: boolean
}

type Choice = { id: string; name: string; group: string | null }

function choicesFor(kind: string, channels: DiscordChannel[] | null, roles: DiscordRole[] | null): Choice[] | null {
  if (kind === "role") return roles && roles.map(r => ({ id: r.id, name: `@${r.name}`, group: null }))
  if (kind === "category") {
    return channels && channels.filter(c => c.type === "category").map(c => ({ id: c.id, name: c.name, group: null }))
  }
  return (
    channels &&
    channels
      .filter(c => c.type === "text" || c.type === "forum")
      .map(c => ({ id: c.id, name: `#${c.name}`, group: c.category }))
  )
}

/** Contrôle côté navigateur, aligné sur `settings_registry.validate` ; l'API reste juge (422). */
export function validateSetting(item: Pick<SettingItem, "key" | "kind">, raw: string): string | null {
  const value = raw.trim()
  if (value === "") return null
  if (isIdKind(item.kind)) return /^\d+$/.test(value) ? null : "Identifiant Discord numérique attendu."
  if (item.kind === "int") return /^\d+$/.test(value) ? null : "Nombre entier positif attendu."
  if (item.kind === "bool") return /^(true|false)$/i.test(value) ? null : "Oui ou non attendu."
  if (item.kind === "url") {
    try {
      const url = new URL(value)
      return url.protocol === "http:" || url.protocol === "https:" ? null : "Adresse http(s) attendue."
    } catch {
      return "Adresse http(s) attendue (https://…)."
    }
  }
  if (ROLE_LIST_KEYS.has(item.key)) {
    return /^\d+(\s*,\s*\d+)*$/.test(value) ? null : "Identifiants de rôles séparés par des virgules."
  }
  return null
}

const sameIds = (a: string, b: string) => {
  const x = new Set(splitIds(a))
  const y = new Set(splitIds(b))
  return x.size === y.size && [...x].every(id => y.has(id))
}

/** Rôles d'une liste par leur nom ; un identifiant absent de Discord est signalé. */
function roleListText(value: string, roles: DiscordRole[]): string {
  return splitIds(value)
    .map(id => {
      const role = roles.find(r => r.id === id)
      return role ? `@${role.name}` : `introuvable (${id})`
    })
    .join(", ")
}

function groupBy(choices: Choice[]): Array<[string | null, Choice[]]> {
  const groups = new Map<string | null, Choice[]>()
  for (const c of choices) groups.set(c.group, [...(groups.get(c.group) ?? []), c])
  return [...groups]
}

/** Un réglage : sélecteur Discord ou saisie validée, enregistrement et retour près du champ. */
export function SettingField({ item, channels, roles, onChannelCreated, readOnly = false }: Props) {
  const ids = useId()
  const [saved, setSaved] = useState(item.value)
  const [draft, setDraft] = useState(item.value)
  const [busy, setBusy] = useState(false)
  const [feedback, setFeedback] = useState<Feedback>(null)

  const choices = isIdKind(item.kind) ? choicesFor(item.kind, channels, roles) : null
  // Liste de rôles : cases à cocher quand la liste Discord est là, saisie d'identifiants sinon.
  const roleList = ROLE_LIST_KEYS.has(item.key)
  const checklist = roleList && roles !== null
  const current = choices?.find(c => c.id === saved)
  // Introuvable : l'API l'a dit pour la valeur chargée, ou la liste fraîche ne la contient pas.
  const missing =
    isIdKind(item.kind) && /^\d+$/.test(saved) && (choices ? !current : item.resolved?.exists === false)
  const unchanged = roleList ? sameIds(draft, saved) : draft.trim() === saved
  // Valeur chargée jamais signalée (un défaut par nom, « Modération », n'est pas une saisie fautive).
  const error = unchanged ? null : validateSetting(item, draft)
  const helpId = `${ids}-help`
  const labelId = `${ids}-label`
  const fieldId = `setting-${item.key}-input`

  async function save(value: string) {
    setBusy(true)
    setFeedback(null)
    try {
      const res = await api.admin.putSetting(item.key, value)
      setSaved(res.value)
      setDraft(res.value)
      const reload = res.bot_reloaded ? "" : " Hermes le prendra en compte sous 5 minutes."
      setFeedback({ kind: "ok", text: (res.value === "" ? "Enregistré : la valeur par défaut s’applique." : "Enregistré.") + reload })
    } catch (e) {
      setFeedback({ kind: "error", text: adminErrorText(e) })
    } finally {
      setBusy(false)
    }
  }

  async function createChannel() {
    setBusy(true)
    setFeedback(null)
    try {
      const ch = await api.admin.createSettingChannel(item.key)
      onChannelCreated({ id: ch.id, name: ch.name, type: item.kind === "category" ? "category" : "text", category: null })
      setSaved(ch.id)
      setDraft(ch.id)
      setFeedback({ kind: "ok", text: `Enregistré : ${item.kind === "category" ? ch.name : `#${ch.name}`} est prêt.` })
    } catch (e) {
      setFeedback({ kind: "error", text: adminErrorText(e) })
    } finally {
      setBusy(false)
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (!busy && !error && !unchanged) void save(draft.trim())
  }

  const currentText =
    saved === ""
      ? "non réglé"
      : checklist
        ? roleListText(saved, roles)
        : missing
        ? `introuvable sur Discord (identifiant ${saved})`
        : current
          ? current.name
          : isIdKind(item.kind) && !/^\d+$/.test(saved)
            ? `« ${saved} » (nom par défaut, aucun choix enregistré)`
            : (item.resolved?.name ?? saved)

  return (
    <form id={`setting-${item.key}`} onSubmit={onSubmit} noValidate className="grid scroll-mt-24 gap-2 border-t border-line pt-4 first:border-t-0 first:pt-0">
      <div className="flex flex-wrap items-center gap-2">
        {readOnly || checklist ? (
          <span id={labelId} className="font-semibold">
            {item.label}
          </span>
        ) : (
          <label htmlFor={fieldId} className="font-semibold">
            {item.label}
          </label>
        )}
        {isKeySetting(item.key) && <Chip color="var(--color-gold)">Important</Chip>}
        {missing && <Chip color="var(--color-orange)">Introuvable</Chip>}
      </div>
      <p className="m-0 text-sm text-muted">
        Actuel : <span className={missing ? "text-orange" : "text-msg"}>{currentText}</span>
      </p>
      {readOnly ? (
        <p className="m-0 text-sm text-muted">
          Réservé aux administrateurs : ce rôle donne des droits (site ou commandes du bot).
        </p>
      ) : (
      <>
      <div className="flex flex-wrap items-start gap-2">
        {checklist ? (
          <RoleChecklist
            id={fieldId}
            labelledBy={labelId}
            describedBy={helpId}
            value={draft}
            roles={roles}
            onChange={value => {
              setDraft(value)
              setFeedback(null)
            }}
          />
        ) : choices ? (
          <select
            id={fieldId}
            value={draft}
            onChange={e => {
              setDraft(e.target.value)
              setFeedback(null)
            }}
            aria-describedby={helpId}
            className={cn(FIELD, "max-w-md flex-1")}
          >
            <option value="">— Non réglé —</option>
            {!choices.some(c => c.id === draft) && draft !== "" && (
              <option value={draft}>{/^\d+$/.test(draft) ? `Introuvable (${draft})` : `« ${draft} » (nom par défaut)`}</option>
            )}
            {groupBy(choices).map(([group, list]) =>
              group ? (
                <optgroup key={group} label={group}>
                  {list.map(c => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </optgroup>
              ) : (
                list.map(c => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))
              ),
            )}
          </select>
        ) : item.kind === "bool" ? (
          <select id={fieldId} value={draft} onChange={e => setDraft(e.target.value)} aria-describedby={helpId} className={cn(FIELD, "max-w-xs")}>
            <option value="">— Par défaut —</option>
            <option value="true">Oui</option>
            <option value="false">Non</option>
          </select>
        ) : (
          <input
            id={fieldId}
            type={item.kind === "url" ? "url" : "text"}
            inputMode={item.kind === "int" || isIdKind(item.kind) ? "numeric" : undefined}
            value={draft}
            onChange={e => {
              setDraft(e.target.value)
              setFeedback(null)
            }}
            aria-invalid={error !== null}
            aria-describedby={helpId}
            placeholder={isIdKind(item.kind) ? "Identifiant Discord" : item.kind === "url" ? "https://…" : undefined}
            className={cn(FIELD, "max-w-md flex-1")}
          />
        )}
        <Button type="submit" size="sm" disabled={busy || unchanged || error !== null}>
          {busy ? "…" : "Enregistrer"}
        </Button>
        {saved !== "" && (
          <Button type="button" size="sm" variant="ghost" disabled={busy} onClick={() => void save("")}>
            Effacer
          </Button>
        )}
        {item.can_create && (saved === "" || missing) && (
          <Button type="button" size="sm" variant="ghost" disabled={busy} onClick={() => void createChannel()}>
            {item.kind === "category" ? "Créer la catégorie" : "Créer le salon"}
          </Button>
        )}
      </div>
      <div id={helpId} className="text-sm">
        {error ? (
          <p className="m-0 text-orange">{error}</p>
        ) : feedback?.kind === "error" ? (
          <p role="alert" className="m-0 text-orange">
            {feedback.text}
          </p>
        ) : feedback?.kind === "ok" ? (
          <p role="status" className="m-0 text-green">
            {feedback.text}
          </p>
        ) : (isIdKind(item.kind) && !choices) || (roleList && !checklist) ? (
          <p className="m-0 text-muted">Liste Discord indisponible (bot muet) : saisis l’identifiant.</p>
        ) : null}
      </div>
      {item.key === "staff_roles" && <ForumsResync />}
      </>
      )}
    </form>
  )
}
