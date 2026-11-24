"use client"

import { ChevronDown, ChevronRight, Plus } from "lucide-react"
import { useId, useState } from "react"
import { Button } from "@/components/ui/button"
import { api } from "@/lib/api/client"
import type { ChannelKind, ChannelsOverview, ManagedChannel, TemplatePreviewResult } from "@/lib/api/types"
import { cn } from "@/lib/cn"
import { plural } from "@/lib/jobs"
import { applyOutcome, ChannelTemplatePanel, channelPrefix, PreviewChanges, TEMPLATE_LABELS } from "./channel-template-panel"
import { channelActionErrorText, FIELD, LABEL } from "./form"

const TYPE_LABELS: Record<ChannelKind, string> = {
  text: "Texte",
  voice: "Vocal",
  forum: "Forum",
  announcement: "Annonces",
  category: "Catégorie",
}

type PanelKind = "access" | "rename" | "move" | "delete"
type Open = { id: string; kind: PanelKind } | null

/** Salons sans catégorie, puis chaque catégorie et ses salons (ordre Discord de l'arbre). */
function group(channels: ManagedChannel[]) {
  return {
    loose: channels.filter(c => c.type !== "category" && !c.parent_id),
    categories: channels
      .filter(c => c.type === "category")
      .map(category => ({ category, children: channels.filter(c => c.parent_id === category.id) })),
  }
}

/** « Rôle requis (Fortnite, Duo) », « Public », « — ». */
function templateSummary(channel: ManagedChannel, overview: ChannelsOverview): string {
  const t = channel.template
  if (!t) return "—"
  const names = t.roles.map(id => overview.roles.find(r => r.id === id)?.name ?? id)
  return t.template === "staff" || names.length === 0 ? TEMPLATE_LABELS[t.template] : `${TEMPLATE_LABELS[t.template]} (${names.join(", ")})`
}

/** Salons du serveur : arborescence, création, renommage, déplacement, suppression, modèles d'accès. */
export function ChannelsAdmin({ initial }: { initial: ChannelsOverview }) {
  const [overview, setOverview] = useState(initial)
  const [open, setOpen] = useState<Open>(null)
  const [creating, setCreating] = useState(false)
  const [collapsed, setCollapsed] = useState<ReadonlySet<string>>(new Set())
  const [success, setSuccess] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [warnings, setWarnings] = useState<string[]>([])
  const createId = useId()
  const { loose, categories } = group(overview.channels)

  /** Relit l'arbre ; en cas d'échec, l'ancien reste affiché. */
  async function reload() {
    try {
      setOverview(await api.admin.channels())
    } catch {
      /* arbre conservé */
    }
  }

  /** Succès (et avertissements d'une application partielle), puis relecture de l'arbre. */
  async function announce(text: string, problems: string[] = []) {
    setError(null)
    setSuccess(text)
    setWarnings(problems)
    await reload()
  }

  const toggle = (id: string, kind: PanelKind) => {
    setCreating(false)
    setOpen(o => (o?.id === id && o.kind === kind ? null : { id, kind }))
  }

  function renderChannel(channel: ManagedChannel, childCount = 0) {
    const isOpen = (kind: PanelKind) => open?.id === channel.id && open.kind === kind
    const panelId = `panel-${channel.id}`
    const name = `${channelPrefix(channel.type)}${channel.name}`
    if (!channel.visible_to_actor) {
      return (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-2.5 text-sm text-muted">
          <span>{name}</span>
          <span>vous ne voyez pas ce salon</span>
        </div>
      )
    }
    return (
      <>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-2.5 text-sm">
          <span className={cn("min-w-40 flex-1", channel.type === "category" ? "font-display font-bold uppercase tracking-wide" : "font-semibold")}>
            {name}
          </span>
          <span className="min-w-40 text-muted">Modèle : {templateSummary(channel, overview)}</span>
          <span className="flex flex-wrap gap-2">
            {(["access", "rename", "move", "delete"] as const)
              .filter(kind => kind !== "move" || channel.type !== "category")
              .map(kind => (
                <Button
                  key={kind}
                  size="sm"
                  variant="ghost"
                  aria-expanded={isOpen(kind)}
                  aria-controls={isOpen(kind) ? panelId : undefined}
                  aria-label={`${ACTION_LABELS[kind]} « ${channel.name} »`}
                  className={kind === "delete" ? "text-orange" : undefined}
                  onClick={() => toggle(channel.id, kind)}
                >
                  {ACTION_LABELS[kind]}
                </Button>
              ))}
          </span>
        </div>
        {open?.id === channel.id && (
          <div id={panelId} className="px-4 pb-4">
            {open.kind === "access" && (
              <ChannelTemplatePanel
                channel={channel}
                childCount={childCount}
                templates={overview.templates}
                roles={overview.roles}
                onApplied={announce}
              />
            )}
            {open.kind === "rename" && (
              <RenameForm
                channel={channel}
                onDone={async text => {
                  setOpen(null)
                  await announce(text)
                }}
              />
            )}
            {open.kind === "move" && (
              <MoveForm
                channel={channel}
                categories={categories.map(c => c.category).filter(c => c.visible_to_actor)}
                onDone={async text => {
                  setOpen(null)
                  await announce(text)
                }}
              />
            )}
            {open.kind === "delete" && (
              <DeleteForm
                channel={channel}
                childCount={childCount}
                onDone={async text => {
                  setOpen(null)
                  await announce(text)
                }}
              />
            )}
          </div>
        )}
      </>
    )
  }

  return (
    <div className="grid gap-6">
      <div className="flex flex-wrap items-center gap-3">
        <Button
          size="sm"
          aria-expanded={creating}
          aria-controls={creating ? createId : undefined}
          onClick={() => {
            setCreating(c => !c)
            setOpen(null)
          }}
        >
          <Plus aria-hidden="true" className="size-4" />
          Nouveau salon
        </Button>
        <p role="status" aria-label="Salons" className="m-0 text-sm text-green">
          {success}
        </p>
        {error && (
          <p role="alert" className="m-0 text-sm text-orange">
            {error}
          </p>
        )}
      </div>
      {warnings.length > 0 && (
        <div role="alert" aria-label="Avertissements">
          <ul className="m-0 grid list-none gap-1 p-0 text-sm text-orange">
            {warnings.map(w => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      {overview.staff_resync && overview.staff_resync.pending > 0 && (
        <StaffResync status={overview.staff_resync} onApplied={announce} />
      )}

      {creating && (
        <CreateForm
          id={createId}
          categories={categories.map(c => c.category).filter(c => c.visible_to_actor)}
          onCancel={() => setCreating(false)}
          onDone={async text => {
            setCreating(false)
            await announce(text)
          }}
        />
      )}

      <ul aria-label="Salons du serveur" className="m-0 grid list-none divide-y divide-line rounded-[20px] border border-line p-0">
        {loose.map(c => (
          <li key={c.id}>{renderChannel(c)}</li>
        ))}
        {categories.map(({ category, children }) => {
          const folded = collapsed.has(category.id)
          const listId = `children-${category.id}`
          return (
            <li key={category.id}>
              <div className="flex items-start">
                <button
                  type="button"
                  aria-expanded={!folded}
                  aria-controls={listId}
                  aria-label={`${folded ? "Déplier" : "Replier"} « ${category.name} »`}
                  onClick={() =>
                    setCollapsed(s => {
                      const next = new Set(s)
                      if (next.has(category.id)) next.delete(category.id)
                      else next.add(category.id)
                      return next
                    })
                  }
                  className="ml-2 mt-2.5 rounded-md p-1 text-muted hover:bg-white/6 hover:text-fg"
                >
                  {folded ? <ChevronRight aria-hidden="true" className="size-4" /> : <ChevronDown aria-hidden="true" className="size-4" />}
                </button>
                <div className="flex-1">{renderChannel(category, children.length)}</div>
              </div>
              {children.length > 0 && (
                <ul id={listId} hidden={folded} aria-label={`Salons de « ${category.name} »`} className="m-0 list-none border-t border-line py-1 pl-8">
                  {children.map(c => (
                    <li key={c.id}>{renderChannel(c)}</li>
                  ))}
                </ul>
              )}
            </li>
          )
        })}
      </ul>
    </div>
  )
}

const ACTION_LABELS: Record<PanelKind, string> = { access: "Accès…", rename: "Renommer", move: "Déplacer", delete: "Supprimer" }

/** État d'un petit formulaire : envoi, erreur affichée. */
function useSubmit(onDone: (text: string) => void | Promise<void>) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  async function run(action: () => Promise<string>) {
    setError(null)
    setBusy(true)
    let text: string
    try {
      text = await action()
    } catch (e) {
      setError(channelActionErrorText(e))
      setBusy(false)
      return
    }
    setBusy(false)
    await onDone(text)
  }
  return { busy, error, setError, run }
}

function FormError({ error }: { error: string | null }) {
  return error ? (
    <p role="alert" className="m-0 text-sm text-orange">
      {error}
    </p>
  ) : null
}

type DoneProps = { onDone: (text: string) => void | Promise<void> }

function CreateForm({ id, categories, onCancel, onDone }: DoneProps & { id: string; categories: ManagedChannel[]; onCancel: () => void }) {
  const ids = useId()
  const [name, setName] = useState("")
  const [type, setType] = useState<ChannelKind>("text")
  const [parent, setParent] = useState("")
  const { busy, error, setError, run } = useSubmit(onDone)

  function submit(e: React.FormEvent) {
    e.preventDefault()
    const trimmed = name.trim()
    if (!trimmed) return setError("Donnez un nom au salon.")
    void run(async () => {
      const created = await api.admin.createChannel({
        name: trimmed,
        type,
        ...(type !== "category" && parent ? { parent_id: parent } : {}),
      })
      return `Salon « ${created.name} » créé.`
    })
  }

  return (
    <section id={id} aria-labelledby={`${ids}-title`} className="grid gap-4 rounded-[20px] border border-line bg-[rgb(19_22_42/0.92)] px-5 py-4">
      <h2 id={`${ids}-title`} className="m-0 font-display text-lg font-bold">
        Nouveau salon
      </h2>
      <form onSubmit={submit} className="grid gap-4 sm:grid-cols-3 sm:items-end">
        <div className="grid gap-1.5">
          <label htmlFor={`${ids}-name`} className={LABEL}>
            Nom
          </label>
          <input
            id={`${ids}-name`}
            className={FIELD}
            value={name}
            maxLength={100}
            aria-describedby={`${ids}-hint`}
            onChange={e => setName(e.target.value)}
          />
        </div>
        <div className="grid gap-1.5">
          <label htmlFor={`${ids}-type`} className={LABEL}>
            Type
          </label>
          <select id={`${ids}-type`} className={FIELD} value={type} onChange={e => setType(e.target.value as ChannelKind)}>
            {(Object.keys(TYPE_LABELS) as ChannelKind[]).map(t => (
              <option key={t} value={t}>
                {TYPE_LABELS[t]}
              </option>
            ))}
          </select>
        </div>
        {type !== "category" && (
          <div className="grid gap-1.5">
            <label htmlFor={`${ids}-parent`} className={LABEL}>
              Catégorie
            </label>
            <select id={`${ids}-parent`} className={FIELD} value={parent} onChange={e => setParent(e.target.value)}>
              <option value="">Aucune</option>
              {categories.map(c => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>
        )}
        <p id={`${ids}-hint`} className="m-0 text-xs text-muted sm:col-span-3">
          1 à 100 caractères. Discord met les noms de salons texte en minuscules, avec des tirets à la place des espaces.
        </p>
        <div className="flex flex-wrap items-center gap-3 sm:col-span-3">
          <Button type="submit" size="sm" disabled={busy}>
            {busy ? "Création…" : "Créer le salon"}
          </Button>
          <Button type="button" size="sm" variant="ghost" onClick={onCancel}>
            Annuler
          </Button>
          <FormError error={error} />
        </div>
      </form>
    </section>
  )
}

function RenameForm({ channel, onDone }: DoneProps & { channel: ManagedChannel }) {
  const ids = useId()
  const [name, setName] = useState(channel.name)
  const { busy, error, setError, run } = useSubmit(onDone)

  function submit(e: React.FormEvent) {
    e.preventDefault()
    const trimmed = name.trim()
    if (!trimmed) return setError("Donnez un nom au salon.")
    if (trimmed === channel.name) return setError("Aucun changement à enregistrer.")
    void run(async () => {
      const result = await api.admin.updateChannel(channel.id, { name: trimmed })
      return `Salon renommé en « ${result.name} ».`
    })
  }

  return (
    <form onSubmit={submit} className="flex flex-wrap items-end gap-3">
      <div className="grid gap-1.5">
        <label htmlFor={`${ids}-name`} className={LABEL}>
          Nouveau nom de « {channel.name} »
        </label>
        <input id={`${ids}-name`} className={FIELD} value={name} maxLength={100} onChange={e => setName(e.target.value)} />
      </div>
      <Button type="submit" size="sm" disabled={busy}>
        {busy ? "Enregistrement…" : "Renommer"}
      </Button>
      <FormError error={error} />
    </form>
  )
}

function MoveForm({ channel, categories, onDone }: DoneProps & { channel: ManagedChannel; categories: ManagedChannel[] }) {
  const ids = useId()
  const [parent, setParent] = useState(channel.parent_id ?? "")
  const { busy, error, setError, run } = useSubmit(onDone)

  function submit(e: React.FormEvent) {
    e.preventDefault()
    if (parent === (channel.parent_id ?? "")) return setError("Le salon est déjà là.")
    void run(async () => {
      await api.admin.updateChannel(channel.id, { parent_id: parent || null })
      const target = categories.find(c => c.id === parent)
      return target ? `« ${channel.name} » déplacé dans « ${target.name} ».` : `« ${channel.name} » sorti de sa catégorie.`
    })
  }

  return (
    <form onSubmit={submit} className="flex flex-wrap items-end gap-3">
      <div className="grid gap-1.5">
        <label htmlFor={`${ids}-parent`} className={LABEL}>
          Catégorie de « {channel.name} »
        </label>
        <select id={`${ids}-parent`} className={FIELD} value={parent} onChange={e => setParent(e.target.value)}>
          <option value="">Aucune (hors catégorie)</option>
          {categories.map(c => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </div>
      <Button type="submit" size="sm" disabled={busy}>
        {busy ? "Déplacement…" : "Déplacer"}
      </Button>
      <FormError error={error} />
    </form>
  )
}

/** Suppression : le nom du salon est retapé (vérifié aussi par web-api). */
function DeleteForm({ channel, childCount, onDone }: DoneProps & { channel: ManagedChannel; childCount: number }) {
  const ids = useId()
  const [typed, setTyped] = useState("")
  const { busy, error, run } = useSubmit(onDone)
  const matches = typed.trim() === channel.name

  function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!matches) return
    void run(async () => {
      await api.admin.deleteChannel(channel.id, typed.trim())
      return `Salon « ${channel.name} » supprimé.`
    })
  }

  return (
    <form onSubmit={submit} className="grid gap-3 rounded-xl border border-orange/40 bg-orange/8 px-4 py-3">
      {channel.type === "category" && childCount > 0 && (
        <p className="m-0 text-sm text-fg">
          Cette catégorie contient {plural(childCount, "salon")} : Discord refusera de la supprimer tant qu’elle n’est pas vide.
        </p>
      )}
      <div className="grid gap-1.5">
        <label htmlFor={`${ids}-confirm`} className={LABEL}>
          Retapez « {channel.name} » pour supprimer définitivement ce salon
        </label>
        <input
          id={`${ids}-confirm`}
          className={FIELD}
          value={typed}
          autoComplete="off"
          onChange={e => setTyped(e.target.value)}
        />
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="submit"
          disabled={!matches || busy}
          className="rounded-[10px] bg-orange px-3 py-[7px] text-[13px] font-bold text-[#1a0c02] disabled:opacity-50"
        >
          {busy ? "Suppression…" : "Supprimer définitivement"}
        </button>
        <FormError error={error} />
      </div>
    </form>
  )
}

/** Bandeau (admin) : `staff_roles` a changé depuis l'application du modèle Staff ; aperçu puis mise à jour. */
function StaffResync({
  status,
  onApplied,
}: {
  status: NonNullable<ChannelsOverview["staff_resync"]>
  onApplied: (text: string, problems: string[]) => void | Promise<void>
}) {
  const ids = useId()
  const [preview, setPreview] = useState<TemplatePreviewResult | null>(null)
  const [busy, setBusy] = useState<"preview" | "apply" | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function runPreview() {
    setError(null)
    setBusy("preview")
    try {
      setPreview(await api.admin.previewStaffResync())
    } catch (e) {
      setError(channelActionErrorText(e))
    } finally {
      setBusy(null)
    }
  }

  async function apply() {
    if (!preview) return
    setError(null)
    setBusy("apply")
    try {
      const { ok, problems } = applyOutcome(await api.admin.applyStaffResync(preview.token))
      setPreview(null)
      await onApplied(ok, problems)
    } catch (e) {
      setPreview(null)
      setError(channelActionErrorText(e))
    } finally {
      setBusy(null)
    }
  }

  return (
    <section aria-labelledby={`${ids}-title`} className="grid gap-3 rounded-[20px] border border-violet/40 bg-violet/8 px-5 py-4">
      <h2 id={`${ids}-title`} className="m-0 font-display text-base font-bold">
        Rôles Staff modifiés
      </h2>
      <p className="m-0 text-sm">
        {plural(status.pending, "salon")} « Staff » {status.pending > 1 ? "gardent" : "garde"} les anciens rôles Staff.
      </p>
      {!status.staff_roles_set ? (
        <p className="m-0 text-sm text-muted">Aucun rôle Staff n’est réglé : choisissez-les dans les Réglages avant de mettre à jour ces salons.</p>
      ) : (
        <div>
          <Button size="sm" variant="ghost" disabled={busy !== null} onClick={() => void runPreview()}>
            {busy === "preview" ? "Aperçu en cours…" : "Mettre à jour les salons Staff"}
          </Button>
        </div>
      )}
      {preview && (
        <div className="grid gap-3 rounded-xl border border-white/10 px-4 py-3">
          <h3 className="m-0 text-sm font-semibold">Aperçu ({plural(preview.count, "salon")})</h3>
          <PreviewChanges preview={preview} />
          <div>
            <Button size="sm" disabled={busy !== null} onClick={() => void apply()}>
              {`Appliquer aux ${plural(preview.count, "salon")}`}
            </Button>
          </div>
        </div>
      )}
      <p role="status" className="m-0 text-sm text-muted">
        {busy === "apply" ? "Mise à jour en cours… (jusqu’à une minute)" : ""}
      </p>
      {error && (
        <p role="alert" className="m-0 text-sm text-orange">
          {error}
        </p>
      )}
    </section>
  )
}
