"use client"

import { useSearchParams } from "next/navigation"
import { useEffect, useId, useState, type FormEvent, type ReactNode } from "react"
import { Button, buttonVariants } from "@/components/ui/button"
import { Chip } from "@/components/ui/chip"
import { Panel } from "@/components/ui/panel"
import { api, auditCsvUrl } from "@/lib/api/client"
import type { AuditEvent, AuditFacets, AuditFilters, AuditPage, Snowflake, UserSearchResult } from "@/lib/api/types"
import {
  KIND_LABELS,
  SHORTCUTS,
  SOURCE_LABELS,
  actionLabel,
  detailEntries,
  eventActionLabel,
  filtersFromParams,
  filtersToParams,
  formatAuditDate,
  sameFilters,
} from "@/lib/audit"
import { cn } from "@/lib/cn"
import { FIELD, adminErrorText } from "./form"

type Props = {
  /** Ouvre la fiche d'un membre (auteur ou cible d'une ligne). */
  onInspect: (user: UserSearchResult) => void
  /** `id` de la fiche membre : cible des liens auteur / cible. */
  inspectorId: string
}

type Loaded = { status: "ok"; page: AuditPage } | { status: "error"; text: string }
type Drafts = { actor: string; target: string; q: string }

const SMALL_LABEL = "text-xs font-semibold text-muted"
const SMALL_FIELD = cn(FIELD, "px-3 py-2 text-sm")

const draftsOf = (f: AuditFilters): Drafts => ({ actor: f.actor ?? "", target: f.target ?? "", q: f.q ?? "" })
const orUndefined = (v: string) => v.trim() || undefined

/** Journal unique : raccourcis, filtres reflétés dans l'URL, tableau paginé et export CSV. */
export function AuditJournal({ onInspect, inspectorId }: Props) {
  const ids = useId()
  const searchParams = useSearchParams()
  const [initial] = useState(() => filtersFromParams(new URLSearchParams(searchParams?.toString())))
  const [filters, setFilters] = useState<AuditFilters>(initial.filters)
  const [page, setPage] = useState(initial.page)
  const [drafts, setDrafts] = useState<Drafts>(() => draftsOf(initial.filters))
  const [loaded, setLoaded] = useState<Loaded | null>(null)
  const [facets, setFacets] = useState<AuditFacets | null>(null)

  useEffect(() => {
    let alive = true
    api.admin
      .auditFacets()
      .then(f => alive && setFacets(f))
      .catch(() => {}) // Menus Action et Salon vides : le reste du journal reste utilisable.
    return () => {
      alive = false
    }
  }, [])

  useEffect(() => {
    let alive = true
    api.admin
      .audit(filters, page)
      .then(p => alive && setLoaded({ status: "ok", page: p }))
      .catch(e => alive && setLoaded({ status: "error", text: adminErrorText(e) }))
    return () => {
      alive = false
    }
  }, [filters, page])

  useEffect(() => {
    const qs = filtersToParams(filters, page).toString()
    window.history.replaceState(window.history.state, "", qs ? `?${qs}` : window.location.pathname)
  }, [filters, page])

  /** Nouveaux filtres : retour à la page 1. */
  function apply(next: AuditFilters) {
    setFilters(next)
    setPage(1)
    setDrafts(draftsOf(next))
  }

  const set = (patch: Partial<AuditFilters>) => apply({ ...filters, ...patch })

  function submitText(e: FormEvent) {
    e.preventDefault()
    set({ actor: orUndefined(drafts.actor), target: orUndefined(drafts.target), q: orUndefined(drafts.q) })
  }

  const kindValue = filters.kind?.join(",") ?? ""
  const singleKind = filters.kind?.length === 1 ? filters.kind[0] : null
  const actionValue = filters.action?.[0] ?? ""
  const actions = singleKind ? [...(facets?.kinds[singleKind] ?? [])] : []
  if (actionValue && !actions.includes(actionValue)) actions.push(actionValue)
  const channels = [...(facets?.channels ?? [])]
  if (filters.channelId && !channels.some(c => c.id === filters.channelId)) {
    channels.push({ id: filters.channelId, name: `#${filters.channelId}` })
  }

  const data = loaded?.status === "ok" ? loaded.page : null

  return (
    <Panel as="section" aria-labelledby={`${ids}-title`} className="grid gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id={`${ids}-title`} className="m-0 font-display text-xl font-extrabold">
          Journal{data ? ` (${data.total})` : ""}
        </h2>
        <a href={auditCsvUrl(filters)} download className={buttonVariants({ variant: "ghost", size: "sm" })}>
          Exporter CSV
        </a>
      </div>

      <div className="flex flex-wrap items-center gap-1.5">
        <span id={`${ids}-shortcuts`} className={SMALL_LABEL}>
          Raccourcis :
        </span>
        <div role="group" aria-labelledby={`${ids}-shortcuts`} className="flex flex-wrap gap-1.5">
          {SHORTCUTS.map(s => {
            const active = sameFilters(filters, s.filters)
            return (
              <button
                key={s.label}
                type="button"
                aria-pressed={active}
                onClick={() => apply(s.filters)}
                className={cn(
                  "rounded-full border px-3 py-1 text-sm font-semibold",
                  active ? "border-violet bg-violet/10 text-violet" : "border-line text-muted hover:text-fg",
                )}
              >
                {s.label}
              </button>
            )
          })}
        </div>
      </div>

      <form onSubmit={submitText} aria-label="Filtres du journal" className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <Field id={`${ids}-kind`} label="Type">
          <select
            id={`${ids}-kind`}
            className={SMALL_FIELD}
            value={kindValue}
            onChange={e => set({ kind: e.target.value ? e.target.value.split(",") : undefined, action: undefined })}
          >
            <option value="">Tous</option>
            {filters.kind && filters.kind.length > 1 && (
              <option value={kindValue}>{filters.kind.map(k => KIND_LABELS[k] ?? k).join(" + ")}</option>
            )}
            {Object.entries(KIND_LABELS).map(([k, label]) => (
              <option key={k} value={k}>
                {label}
              </option>
            ))}
          </select>
        </Field>
        <Field id={`${ids}-action`} label="Action">
          <select
            id={`${ids}-action`}
            className={SMALL_FIELD}
            value={actionValue}
            disabled={!singleKind}
            onChange={e => set({ action: e.target.value ? [e.target.value] : undefined })}
          >
            <option value="">Toutes</option>
            {actions.map(a => (
              <option key={a} value={a}>
                {actionLabel(a)}
              </option>
            ))}
          </select>
        </Field>
        <Field id={`${ids}-source`} label="Source">
          <select
            id={`${ids}-source`}
            className={SMALL_FIELD}
            value={filters.source?.join(",") ?? ""}
            onChange={e => set({ source: e.target.value ? [e.target.value] : undefined })}
          >
            <option value="">Toutes</option>
            {Object.entries(SOURCE_LABELS).map(([s, label]) => (
              <option key={s} value={s}>
                {label}
              </option>
            ))}
          </select>
        </Field>
        <Field id={`${ids}-channel`} label="Salon">
          <select
            id={`${ids}-channel`}
            className={SMALL_FIELD}
            value={filters.channelId ?? ""}
            onChange={e => set({ channelId: e.target.value || undefined })}
          >
            <option value="">Tous</option>
            {channels.map(c => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </Field>
        <Field id={`${ids}-from`} label="Du">
          <input
            id={`${ids}-from`}
            type="date"
            className={SMALL_FIELD}
            value={filters.from ?? ""}
            max={filters.to}
            onChange={e => set({ from: e.target.value || undefined })}
          />
        </Field>
        <Field id={`${ids}-to`} label="Au">
          <input
            id={`${ids}-to`}
            type="date"
            className={SMALL_FIELD}
            value={filters.to ?? ""}
            min={filters.from}
            onChange={e => set({ to: e.target.value || undefined })}
          />
        </Field>
        <Field id={`${ids}-actor`} label="Auteur">
          <input
            id={`${ids}-actor`}
            className={SMALL_FIELD}
            value={drafts.actor}
            placeholder="Nom ou ID"
            onChange={e => setDrafts(d => ({ ...d, actor: e.target.value }))}
          />
        </Field>
        <Field id={`${ids}-target`} label="Cible">
          <input
            id={`${ids}-target`}
            className={SMALL_FIELD}
            value={drafts.target}
            placeholder="Nom ou ID"
            onChange={e => setDrafts(d => ({ ...d, target: e.target.value }))}
          />
        </Field>
        <Field id={`${ids}-q`} label="Rechercher" className="col-span-2">
          <input
            id={`${ids}-q`}
            type="search"
            className={SMALL_FIELD}
            value={drafts.q}
            placeholder="Rechercher…"
            onChange={e => setDrafts(d => ({ ...d, q: e.target.value }))}
          />
        </Field>
        <label className="flex items-center gap-2 self-end py-2 text-sm">
          <input
            type="checkbox"
            className="size-4 accent-violet"
            checked={filters.failedOnly ?? false}
            onChange={e => set({ failedOnly: e.target.checked || undefined })}
          />
          Échecs seulement
        </label>
        <Button type="submit" size="sm" variant="ghost" className="self-end">
          Appliquer
        </Button>
      </form>

      {!loaded && <p className="m-0 text-sm text-muted">Chargement…</p>}
      {loaded?.status === "error" && (
        <p role="alert" className="m-0 text-sm text-orange">
          {loaded.text}
        </p>
      )}
      {data && data.events.length === 0 && <p className="m-0 text-sm text-muted">Aucun évènement pour ces filtres.</p>}
      {data && data.events.length > 0 && (
        <div role="region" aria-labelledby={`${ids}-title`} tabIndex={0} className="overflow-x-auto rounded-xl border border-line">
          <table className="w-full border-collapse text-left text-sm">
            <caption className="sr-only">
              Évènements du journal, page {data.page} sur {data.pages}
            </caption>
            <thead className="text-xs text-muted">
              <tr>
                {["Date (Europe/Paris)", "Type", "Action", "Auteur", "Cible", "Salon", "Détail"].map(h => (
                  <th key={h} scope="col" className="border-b border-line px-3 py-2 font-semibold whitespace-nowrap">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.events.map(ev => (
                <Row key={ev.id} event={ev} onInspect={onInspect} inspectorId={inspectorId} />
              ))}
            </tbody>
          </table>
        </div>
      )}
      {data && data.pages > 1 && (
        <div className="flex items-center justify-center gap-3">
          <Button size="sm" variant="ghost" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>
            Précédent
          </Button>
          <span className="text-sm text-muted">
            Page {data.page} / {data.pages}
          </span>
          <Button size="sm" variant="ghost" disabled={page >= data.pages} onClick={() => setPage(p => p + 1)}>
            Suivant
          </Button>
        </div>
      )}
    </Panel>
  )
}

function Field({ id, label, className, children }: { id: string; label: string; className?: string; children: ReactNode }) {
  return (
    <div className={cn("grid gap-1", className)}>
      <label htmlFor={id} className={SMALL_LABEL}>
        {label}
      </label>
      {children}
    </div>
  )
}

const CELL = "border-b border-line/60 px-3 py-2 align-top"

function Row({ event, onInspect, inspectorId }: { event: AuditEvent } & Props) {
  const entries = detailEntries(event)
  return (
    <tr>
      <td className={cn(CELL, "whitespace-nowrap tabular-nums")}>
        <time dateTime={event.occurred_at}>{formatAuditDate(event.occurred_at)}</time>
      </td>
      <td className={CELL}>
        <span className="block font-semibold">{KIND_LABELS[event.kind] ?? event.kind}</span>
        <span className="block text-xs text-muted">via {SOURCE_LABELS[event.source] ?? event.source}</span>
      </td>
      <td className={CELL}>
        <span className="flex flex-wrap items-center gap-1.5">
          <span>{eventActionLabel(event)}</span>
          {!event.success && <Chip color="#FF5A5A">échec</Chip>}
        </span>
      </td>
      <td className={CELL}>
        <Person id={event.actor_id} name={event.actor_name} onInspect={onInspect} inspectorId={inspectorId} />
      </td>
      <td className={CELL}>
        <Person id={event.target_id} name={event.target_name} onInspect={onInspect} inspectorId={inspectorId} />
      </td>
      <td className={CELL}>{event.channel_name ?? (event.channel_id ? `#${event.channel_id}` : "—")}</td>
      <td className={cn(CELL, "min-w-56")}>
        {entries.length === 0 ? (
          "—"
        ) : (
          <details>
            <summary className="cursor-pointer text-muted hover:text-fg">Détail ({entries.length})</summary>
            <dl className="m-0 mt-2 grid gap-1.5">
              {entries.map((d, i) => (
                <div key={i}>
                  <dt className="text-xs text-muted">{d.label}</dt>
                  <dd className="m-0 break-words whitespace-pre-wrap">{d.value}</dd>
                </div>
              ))}
            </dl>
          </details>
        )}
      </td>
    </tr>
  )
}

function Person({ id, name, onInspect, inspectorId }: { id: Snowflake | null; name: string | null } & Props) {
  if (!id) return <>{name ?? "—"}</>
  const label = name ?? id
  return (
    <a
      href={`#${inspectorId}`}
      onClick={() => onInspect({ user_id: id, username: label, discord_avatar: null })}
      className="font-semibold text-fg underline decoration-violet/50 underline-offset-2 hover:decoration-violet"
    >
      {label}
    </a>
  )
}
