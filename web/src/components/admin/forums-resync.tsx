"use client"

import { useId, useState } from "react"
import { Button } from "@/components/ui/button"
import { api } from "@/lib/api/client"
import type { ForumOverwrite, ForumResyncPreview } from "@/lib/api/types"
import { botActionErrorText, type Feedback } from "./form"

type Phase =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "confirm"; forums: number; details: ForumResyncPreview[] }
  | { kind: "running"; forums: number }

const forumsText = (n: number) => `${n} forum${n > 1 ? "s" : ""} de jeux`

/** Permissions posées par Hermes sur les forums de jeux (`bot/utils/games.forum_overwrites`). */
const PERMISSION_LABEL: Record<string, string> = {
  view_channel: "voir le salon",
  send_messages: "écrire",
  send_messages_in_threads: "écrire dans les fils",
  create_public_threads: "créer des fils",
  manage_threads: "gérer les fils",
  manage_messages: "gérer les messages",
  manage_channels: "gérer le salon",
  manage_roles: "gérer les permissions",
  read_message_history: "lire l’historique",
  embed_links: "intégrer des liens",
  attach_files: "joindre des fichiers",
  add_reactions: "ajouter des réactions",
}

const CHANGE_LABEL = { removed: "retirée", modified: "modifiée", added: "ajoutée" } as const

export function overwriteText(o: ForumOverwrite | null): string {
  if (!o || (o.allow.length === 0 && o.deny.length === 0)) return "aucune"
  const label = (p: string) => PERMISSION_LABEL[p] ?? p
  const parts = o.allow.map(label)
  if (o.deny.length) parts.push(`refusé : ${o.deny.map(label).join(", ")}`)
  return parts.join(", ")
}

function ForumChanges({ forum }: { forum: ForumResyncPreview }) {
  const labelId = useId()
  return (
    <li aria-labelledby={labelId} className="grid gap-1">
      <span id={labelId} className="text-sm font-semibold">
        #{forum.forum} ({forum.game})
      </span>
      {forum.changes.length === 0 ? (
        <span className="text-sm text-muted">Déjà à jour.</span>
      ) : (
        <ul className="m-0 grid gap-0.5 pl-4 text-sm">
          {forum.changes.map(c => (
            <li key={`${c.kind}-${c.target}`}>
              {`${c.kind === "role" ? "@" : "membre "}${c.target} : surcharge ${CHANGE_LABEL[c.change]} (${overwriteText(c.before)} → ${overwriteText(c.after)})`}
            </li>
          ))}
        </ul>
      )}
    </li>
  )
}

/**
 * « Mettre à jour les forums » (réservé admin) : après un changement de `staff_roles`, réécrit les
 * permissions des forums de jeux. L'aperçu (lecture seule) liste chaque forum et les surcharges retirées,
 * modifiées ou ajoutées ; la confirmation porte ce nombre de forums, puis l'action (jusqu'à 70 s).
 * `blocked` : la liste du staff est modifiée mais pas encore enregistrée.
 */
export function ForumsResync({ blocked = false }: { blocked?: boolean }) {
  const [phase, setPhase] = useState<Phase>({ kind: "idle" })
  const [feedback, setFeedback] = useState<Feedback>(null)

  async function preview() {
    setPhase({ kind: "loading" })
    setFeedback(null)
    try {
      const { forums, details } = await api.admin.gameForumsPreview()
      if (forums === 0) {
        setPhase({ kind: "idle" })
        setFeedback({ kind: "ok", text: "Aucun forum de jeu à mettre à jour." })
      } else setPhase({ kind: "confirm", forums, details: details ?? [] })
    } catch (e) {
      setPhase({ kind: "idle" })
      setFeedback({ kind: "error", text: botActionErrorText(e) })
    }
  }

  async function confirm(forums: number) {
    setPhase({ kind: "running", forums })
    try {
      const res = await api.admin.resyncGameForums(forums)
      const failed = res.failed ?? []
      const done = `Permissions réécrites : ${forumsText(res.forums)}.`
      setFeedback(
        failed.length
          ? {
              kind: "error",
              text: `${done} Échec pour ${failed.map(f => `#${f.forum} (${f.error})`).join(", ")} : relance pour réessayer.`,
            }
          : { kind: "ok", text: done },
      )
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
        de ces rôles, mets à jour les forums existants : toute autre surcharge est retirée.
      </p>
      {phase.kind === "confirm" ? (
        <div role="group" aria-label="Confirmer la mise à jour des forums" className="grid gap-2">
          <span className="text-sm">Réécrire les permissions de {forumsText(phase.forums)} ?</span>
          {phase.details.length > 0 && <ul className="m-0 grid list-none gap-2 p-0">{phase.details.map(f => <ForumChanges key={f.key} forum={f} />)}</ul>}
          <div className="flex flex-wrap items-center gap-2">
            <Button size="sm" onClick={() => void confirm(phase.forums)}>
              Confirmer
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setPhase({ kind: "idle" })}>
              Annuler
            </Button>
          </div>
        </div>
      ) : (
        <div className="flex flex-wrap items-center gap-2">
          <Button size="sm" variant="ghost" disabled={blocked || phase.kind !== "idle"} onClick={() => void preview()}>
            Mettre à jour les forums
          </Button>
          {blocked && <span className="text-sm text-muted">Enregistre d’abord la nouvelle liste du staff.</span>}
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
