"use client"

import { useEffect, useId, useState } from "react"
import { Avatar } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import { Panel } from "@/components/ui/panel"
import { api } from "@/lib/api/client"
import type { AdminWarn } from "@/lib/api/types"
import { ConfirmButton } from "./confirm-button"
import { adminErrorText, FIELD } from "./form"

/** Date d'une sanction (`create_time` : secondes Unix). */
export const warnDate = (seconds: number) =>
  new Date(seconds * 1000).toLocaleString("fr-FR", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })

/** Toutes les sanctions du serveur, filtrables par pseudo ou raison. */
export function WarnsList({ refreshKey }: { refreshKey: number }) {
  const ids = useId()
  const [warns, setWarns] = useState<AdminWarn[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState("")
  // « Actualiser » : relecture à la demande, en plus des relectures après une sanction.
  const [reloads, setReloads] = useState(0)

  useEffect(() => {
    let alive = true
    api.admin
      .allWarns()
      .then(r => {
        if (!alive) return
        setWarns(r.warns)
        setError(null)
      })
      .catch(e => alive && setError(adminErrorText(e)))
    return () => {
      alive = false
    }
  }, [refreshKey, reloads])

  async function remove(id: number) {
    setError(null)
    try {
      await api.admin.deleteWarn(id)
      setWarns(list => list && list.filter(w => w.id !== id))
    } catch (e) {
      setError(adminErrorText(e))
    }
  }

  const needle = filter.trim().toLowerCase()
  const shown = (warns ?? []).filter(
    w => !needle || w.username.toLowerCase().includes(needle) || w.reason.toLowerCase().includes(needle),
  )

  return (
    <Panel as="section" aria-labelledby={`${ids}-title`} className="grid gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id={`${ids}-title`} className="m-0 font-display text-xl font-extrabold">
          Sanctions du serveur{warns ? ` (${warns.length})` : ""}
        </h2>
        <Button size="sm" variant="ghost" onClick={() => setReloads(n => n + 1)}>
          Actualiser
        </Button>
      </div>
      <label className="sr-only" htmlFor={`${ids}-filter`}>
        Filtrer les sanctions
      </label>
      <input
        id={`${ids}-filter`}
        value={filter}
        onChange={e => setFilter(e.target.value)}
        placeholder="Filtrer par pseudo ou raison…"
        className={`${FIELD} max-w-sm`}
      />
      {error && (
        <p role="alert" className="m-0 text-sm text-orange">
          {error}
        </p>
      )}
      {warns === null && !error && <p className="m-0 text-sm text-muted">Chargement…</p>}
      {warns !== null && shown.length === 0 && <p className="m-0 text-sm text-muted">Aucune sanction trouvée.</p>}
      {shown.length > 0 && (
        <ul className="m-0 grid max-h-[560px] list-none gap-2 overflow-y-auto p-0 pr-1">
          {shown.map(w => (
            <li key={w.id} className="flex flex-wrap items-center gap-3 rounded-xl border border-line px-4 py-3">
              <Avatar name={w.username} src={w.discord_avatar} size={32} />
              <div className="min-w-0 flex-1">
                <p className="m-0 text-sm font-semibold">{w.username}</p>
                <p className="m-0 truncate text-sm text-msg">{w.reason}</p>
                <p className="m-0 text-xs text-muted">
                  {warnDate(w.create_time)}
                  {w.moderator_username ? ` · par ${w.moderator_username}` : ""}
                </p>
              </div>
              <ConfirmButton question="Retirer cette sanction ?" confirmLabel="Retirer" onConfirm={() => remove(w.id)}>
                Retirer
              </ConfirmButton>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  )
}
