"use client"

import { useId, useState, type FormEvent } from "react"
import { GAMES_MAX, MOTTO_MAX } from "@/components/staff/staff-profile-form"
import { Avatar } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import { Panel } from "@/components/ui/panel"
import { api } from "@/lib/api/client"
import type { Game, StaffMember } from "@/lib/api/types"
import { cn } from "@/lib/cn"
import { adminErrorText, FIELD, type Feedback } from "./form"

const length = (text: string) => [...text].length
const LINE_BREAKS = new RegExp(`[\\r\\n${String.fromCharCode(0x2028, 0x2029)}]+`, "g")

/** Carte d'un membre du staff : phrase et jeux (`PUT /admin/staff/{id}`). */
function StaffCardEditor({ member, games }: { member: StaffMember; games: Game[] | null }) {
  const ids = useId()
  const [motto, setMotto] = useState(member.motto ?? "")
  const [selected, setSelected] = useState(member.games)
  const [busy, setBusy] = useState(false)
  const [feedback, setFeedback] = useState<Feedback>(null)

  const trimmed = motto.trim()
  const error =
    length(trimmed) > MOTTO_MAX
      ? `Phrase : ${MOTTO_MAX} caractères maximum.`
      : selected.length > GAMES_MAX
        ? `${GAMES_MAX} jeux maximum.`
        : null

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (error || busy) return
    setBusy(true)
    setFeedback(null)
    try {
      await api.admin.updateStaffProfile(member.id, { motto: trimmed || null, games: selected })
      setFeedback({ kind: "ok", text: "Enregistré. L’état-major public se met à jour sous quelques minutes." })
    } catch (err) {
      setFeedback({ kind: "error", text: adminErrorText(err) })
    } finally {
      setBusy(false)
    }
  }

  const toggle = (key: string) => {
    setFeedback(null)
    setSelected(list => (list.includes(key) ? list.filter(k => k !== key) : [...list, key]))
  }

  return (
    <Panel as="li" className="grid content-start gap-4">
      <form onSubmit={submit} noValidate className="grid gap-4" aria-labelledby={`${ids}-name`}>
        <div className="flex items-center gap-3">
          <Avatar name={member.name} src={member.avatar} size={40} />
          <div>
            <p id={`${ids}-name`} className="m-0 font-semibold">
              {member.name}
            </p>
            <p className="m-0 text-sm text-muted">{member.role ?? "Staff"}</p>
          </div>
        </div>
        <div className="grid gap-1.5">
          <label htmlFor={`${ids}-motto`} className="text-sm font-semibold">
            Phrase de {member.name}
          </label>
          <input
            id={`${ids}-motto`}
            value={motto}
            onChange={e => {
              setFeedback(null)
              setMotto(e.target.value.replace(LINE_BREAKS, " "))
            }}
            aria-invalid={length(trimmed) > MOTTO_MAX}
            className={FIELD}
          />
          <span className={cn("text-xs tabular-nums", length(trimmed) > MOTTO_MAX ? "text-orange" : "text-muted")}>
            {length(trimmed)} / {MOTTO_MAX}
          </span>
        </div>
        <fieldset className="m-0 grid gap-2 border-0 p-0">
          <legend className="mb-1 p-0 text-sm font-semibold">Jeux ({selected.length} / {GAMES_MAX})</legend>
          {games === null ? (
            <p className="m-0 text-sm text-muted">Liste des jeux indisponible : les jeux actuels sont conservés.</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {games.map(g => (
                <label key={g.key} className="inline-flex items-center gap-1.5 rounded-full border border-white/14 px-3 py-1.5 text-sm">
                  <input type="checkbox" checked={selected.includes(g.key)} onChange={() => toggle(g.key)} className="size-4 accent-violet" />
                  {g.name}
                </label>
              ))}
            </div>
          )}
        </fieldset>
        {error && <p className="m-0 text-sm text-orange">{error}</p>}
        <div className="flex flex-wrap items-center gap-3">
          <Button type="submit" size="sm" disabled={busy || error !== null}>
            {busy ? "…" : "Enregistrer"}
          </Button>
          {feedback && (
            <p role={feedback.kind === "error" ? "alert" : "status"} className={cn("m-0 text-sm", feedback.kind === "error" ? "text-orange" : "text-green")}>
              {feedback.text}
            </p>
          )}
        </div>
      </form>
    </Panel>
  )
}

export function StaffEditor({ staff, games }: { staff: StaffMember[]; games: Game[] | null }) {
  if (staff.length === 0) return <p className="m-0 text-muted">Personne dans l’état-major pour l’instant.</p>
  return (
    <ul className="m-0 grid list-none gap-6 p-0 lg:grid-cols-2">
      {staff.map(m => (
        <StaffCardEditor key={m.id} member={m} games={games} />
      ))}
    </ul>
  )
}
