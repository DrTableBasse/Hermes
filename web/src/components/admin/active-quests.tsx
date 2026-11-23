"use client"

import { useId, useState } from "react"
import { Panel } from "@/components/ui/panel"
import { api } from "@/lib/api/client"
import type { ActiveQuest } from "@/lib/api/types"
import { cn } from "@/lib/cn"
import { formatDate } from "@/lib/format"
import { ConfirmButton } from "./confirm-button"
import { adminErrorText, FIELD, LABEL, type Feedback } from "./form"
import { questTypeLabel } from "./quest-form"

/** Quêtes de la semaine et déploiement d'un nouveau tirage (remplace les quêtes en cours). */
export function ActiveQuests({ quests: initial }: { quests: ActiveQuest[] | null }) {
  const ids = useId()
  const [quests, setQuests] = useState(initial)
  const [count, setCount] = useState("8")
  const [busy, setBusy] = useState(false)
  const [feedback, setFeedback] = useState<Feedback>(null)
  const n = Number(count)
  const countError = Number.isInteger(n) && n >= 1 && n <= 20 ? null : "De 1 à 20 quêtes."

  async function deploy() {
    setBusy(true)
    setFeedback(null)
    try {
      const res = await api.admin.deployQuests(n)
      setFeedback({ kind: "ok", text: `${res.deployed} quête(s) déployée(s) pour la semaine du ${formatDate(res.week_start)}.` })
      try {
        setQuests((await api.admin.activeQuests()).quests)
      } catch {
        setQuests(null)
      }
    } catch (e) {
      setFeedback({ kind: "error", text: adminErrorText(e) })
    } finally {
      setBusy(false)
    }
  }

  return (
    <Panel as="section" aria-labelledby={`${ids}-title`} className="grid gap-4">
      <h2 id={`${ids}-title`} className="m-0 font-display text-xl font-extrabold">
        Quêtes de la semaine
      </h2>
      <div className="flex flex-wrap items-end gap-3">
        <div className="grid gap-1.5">
          <label htmlFor={`${ids}-count`} className={LABEL}>
            Nombre à tirer
          </label>
          <input
            id={`${ids}-count`}
            inputMode="numeric"
            value={count}
            onChange={e => setCount(e.target.value)}
            aria-invalid={countError !== null}
            className={cn(FIELD, "w-24")}
          />
        </div>
        <ConfirmButton
          danger={false}
          size="md"
          question="Remplacer les quêtes en cours par un nouveau tirage ?"
          confirmLabel="Déployer"
          disabled={busy || countError !== null}
          onConfirm={deploy}
        >
          {busy ? "Déploiement…" : "Déployer de nouvelles quêtes"}
        </ConfirmButton>
      </div>
      {countError && <p className="m-0 text-sm text-orange">{countError}</p>}
      {feedback && (
        <p role={feedback.kind === "error" ? "alert" : "status"} className={cn("m-0 text-sm", feedback.kind === "error" ? "text-orange" : "text-green")}>
          {feedback.text}
        </p>
      )}
      {quests === null ? (
        <p role="alert" className="m-0 text-sm text-orange">
          Quêtes de la semaine illisibles pour l’instant.
        </p>
      ) : quests.length === 0 ? (
        <p className="m-0 text-sm text-muted">Aucune quête active cette semaine.</p>
      ) : (
        <ul className="m-0 grid list-none gap-2 p-0">
          {quests.map(q => (
            <li key={q.id} className="flex flex-wrap items-center gap-3 rounded-xl border border-line px-4 py-3">
              <span className="text-xl" aria-hidden="true">
                {q.icon}
              </span>
              <div className="min-w-0 flex-1">
                <p className="m-0 text-sm font-semibold">{q.title}</p>
                <p className="m-0 text-xs text-muted">
                  {questTypeLabel(q.quest_type)} · objectif {q.target_value} · +{q.xp_reward} XP
                </p>
              </div>
              <p className="m-0 text-xs text-muted tabular-nums">
                {Number(q.participant_count)} participant(s) · {Number(q.completed_count)} terminée(s)
              </p>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  )
}
