"use client"

import { useEffect, useId, useState } from "react"
import { Button } from "@/components/ui/button"
import { Chip } from "@/components/ui/chip"
import { Panel } from "@/components/ui/panel"
import { api } from "@/lib/api/client"
import type { AdminLog, AdminLogPage } from "@/lib/api/types"
import { cn } from "@/lib/cn"
import { formatDate } from "@/lib/format"
import { adminErrorText } from "./form"

const TABS = [
  { key: "all", label: "Tout", types: undefined },
  { key: "moderation", label: "Modération", types: ["warn", "kick", "ban", "timeout", "delete_warn"] },
  { key: "commands", label: "Commandes", types: ["command_toggle"] },
] as const
type Tab = (typeof TABS)[number]["key"]

const ACTIONS: Record<string, { label: string; color: string }> = {
  warn: { label: "Avertissement", color: "var(--color-gold)" },
  kick: { label: "Expulsion", color: "var(--color-orange)" },
  ban: { label: "Bannissement", color: "#FF5A5A" },
  timeout: { label: "Exclusion temp.", color: "var(--color-violet)" },
  delete_warn: { label: "Sanction retirée", color: "var(--color-muted)" },
  command_toggle: { label: "Commande", color: "var(--color-blue)" },
}

function describe(log: AdminLog): string {
  const d = log.details as { reason?: unknown; duration_minutes?: unknown; command_name?: unknown; enabled?: unknown }
  if (log.action_type === "command_toggle" && typeof d.command_name === "string") {
    return `/${d.command_name} ${d.enabled === false ? "coupée" : "activée"}`
  }
  const parts = []
  if (typeof d.reason === "string" && d.reason) parts.push(d.reason)
  if (typeof d.duration_minutes === "number") parts.push(`${d.duration_minutes} min`)
  return parts.join(" · ")
}

/** Journal des actions d'administration, par catégorie et paginé (50 par page côté API). */
export function AdminLogs() {
  const ids = useId()
  const [tab, setTab] = useState<Tab>("all")
  const [page, setPage] = useState(1)
  const [data, setData] = useState<AdminLogPage | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    const types = TABS.find(x => x.key === tab)?.types
    api.admin
      .logs(page, types ? [...types] : undefined)
      .then(d => {
        if (!alive) return
        setData(d)
        setError(null)
      })
      .catch(e => alive && setError(adminErrorText(e)))
    return () => {
      alive = false
    }
  }, [tab, page])

  return (
    <Panel as="section" aria-labelledby={`${ids}-title`} className="grid gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id={`${ids}-title`} className="m-0 font-display text-xl font-extrabold">
          Journal{data ? ` (${data.total})` : ""}
        </h2>
        <div role="group" aria-label="Catégorie du journal" className="flex gap-1.5">
          {TABS.map(t => (
            <button
              key={t.key}
              type="button"
              aria-pressed={tab === t.key}
              onClick={() => {
                setTab(t.key)
                setPage(1)
              }}
              className={cn(
                "rounded-full border px-3 py-1 text-sm font-semibold",
                tab === t.key ? "border-violet bg-violet/10 text-violet" : "border-line text-muted hover:text-fg",
              )}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>
      {error && (
        <p role="alert" className="m-0 text-sm text-orange">
          {error}
        </p>
      )}
      {data && data.logs.length === 0 && <p className="m-0 text-sm text-muted">Aucune action dans cette catégorie.</p>}
      {data && data.logs.length > 0 && (
        <ul className="m-0 grid list-none gap-2 p-0">
          {data.logs.map(log => {
            const meta = ACTIONS[log.action_type] ?? { label: log.action_type, color: "var(--color-muted)" }
            const detail = describe(log)
            return (
              <li key={log.id} className="flex flex-wrap items-start gap-3 rounded-xl border border-line px-4 py-3">
                <Chip color={meta.color}>{meta.label}</Chip>
                <div className="min-w-0 flex-1 text-sm">
                  <p className="m-0">
                    <span className="font-semibold">{log.actor_name ?? log.actor_id ?? "?"}</span>
                    {log.target_name && <span className="text-msg"> → {log.target_name}</span>}
                  </p>
                  {detail && <p className="m-0 truncate text-muted">{detail}</p>}
                </div>
                <time dateTime={log.created_at} className="text-xs whitespace-nowrap text-muted">
                  {formatDate(log.created_at)}
                </time>
              </li>
            )
          })}
        </ul>
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
