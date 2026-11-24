"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { api } from "@/lib/api/client"
import { botActionErrorText, type Feedback } from "./form"

type Phase = { kind: "idle" } | { kind: "loading" } | { kind: "confirm"; forums: number } | { kind: "running"; forums: number }

const forumsText = (n: number) => `${n} forum${n > 1 ? "s" : ""} de jeux`

/**
 * « Mettre à jour les forums » (réservé admin) : après un changement de `staff_roles`, réécrit les
 * permissions des forums de jeux. Aperçu du nombre, confirmation de ce nombre, puis action (jusqu'à 70 s).
 */
export function ForumsResync() {
  const [phase, setPhase] = useState<Phase>({ kind: "idle" })
  const [feedback, setFeedback] = useState<Feedback>(null)

  async function preview() {
    setPhase({ kind: "loading" })
    setFeedback(null)
    try {
      const { forums } = await api.admin.gameForumsPreview()
      if (forums === 0) {
        setPhase({ kind: "idle" })
        setFeedback({ kind: "ok", text: "Aucun forum de jeu à mettre à jour." })
      } else setPhase({ kind: "confirm", forums })
    } catch (e) {
      setPhase({ kind: "idle" })
      setFeedback({ kind: "error", text: botActionErrorText(e) })
    }
  }

  async function confirm(forums: number) {
    setPhase({ kind: "running", forums })
    try {
      const res = await api.admin.resyncGameForums(forums)
      setFeedback({ kind: "ok", text: `Permissions réécrites : ${forumsText(res.forums)}.` })
    } catch (e) {
      setFeedback({ kind: "error", text: botActionErrorText(e) })
    } finally {
      setPhase({ kind: "idle" })
    }
  }

  return (
    <div className="grid gap-2 rounded-xl border border-line p-3">
      <p className="m-0 text-sm text-muted">
        Les forums de jeux ne sont ouverts qu’au rôle du jeu, aux rôles du staff et à Hermes. Après un changement
        de ces rôles, mets à jour les forums existants.
      </p>
      {phase.kind === "confirm" ? (
        <div role="group" aria-label="Confirmer la mise à jour des forums" className="flex flex-wrap items-center gap-2">
          <span className="text-sm">Réécrire les permissions de {forumsText(phase.forums)} ?</span>
          <Button size="sm" onClick={() => void confirm(phase.forums)}>
            Confirmer
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setPhase({ kind: "idle" })}>
            Annuler
          </Button>
        </div>
      ) : (
        <div>
          <Button size="sm" variant="ghost" disabled={phase.kind !== "idle"} onClick={() => void preview()}>
            Mettre à jour les forums
          </Button>
        </div>
      )}
      {phase.kind === "running" ? (
        <p role="status" className="m-0 text-sm text-muted">
          Mise à jour de {forumsText(phase.forums)} en cours… (jusqu’à une minute)
        </p>
      ) : (
        feedback && (
          <p role={feedback.kind === "error" ? "alert" : "status"} className={feedback.kind === "error" ? "m-0 text-sm text-orange" : "m-0 text-sm text-green"}>
            {feedback.text}
          </p>
        )
      )}
    </div>
  )
}
