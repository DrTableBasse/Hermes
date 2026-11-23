"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { XpBar } from "@/components/ui/xp-bar"
import { api } from "@/lib/api/client"
import type { Quest, QuestStatus } from "@/lib/api/types"
import { cn } from "@/lib/cn"
import { formatNumber } from "@/lib/format"

/** Quête de la semaine ; réclame sa récompense (`POST /quests/{id}/claim`) une fois terminée. */
export function QuestCard({ quest }: { quest: Quest }) {
  const [status, setStatus] = useState<QuestStatus>(quest.status)
  const [pending, setPending] = useState(false)
  const [failed, setFailed] = useState(false)

  const claimed = status === "claimed"
  const done = status !== "active"
  const ratio = done ? 1 : quest.target_value > 0 ? quest.current_progress / quest.target_value : 0
  const percent = Math.min(100, Math.round(ratio * 100))

  async function claim() {
    setPending(true)
    setFailed(false)
    try {
      await api.quests.claim(quest.id)
      setStatus("claimed")
    } catch {
      setFailed(true)
    } finally {
      setPending(false)
    }
  }

  return (
    <li className={cn("grid gap-3 rounded-[20px] border bg-[rgb(19_22_42/0.92)] p-5", claimed ? "border-green/40" : "border-line")}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="m-0 text-sm font-semibold">{quest.title}</h3>
          {quest.description && <p className="m-0 mt-0.5 text-xs text-muted">{quest.description}</p>}
        </div>
        <span className={cn("font-display text-sm font-bold whitespace-nowrap", done ? "text-green" : "text-cyan")}>
          +{formatNumber(quest.xp_reward)} XP
        </span>
      </div>
      <div>
        <div className="mb-1.5 flex justify-between text-xs text-muted tabular-nums">
          <span>
            {formatNumber(quest.current_progress)} sur {formatNumber(quest.target_value)}
          </span>
          <span>{percent} %</span>
        </div>
        <XpBar
          ratio={ratio}
          color={done ? "var(--color-green)" : undefined}
          label={`Avancement de la quête « ${quest.title} »`}
        />
      </div>
      {status === "completed" && (
        <Button type="button" size="sm" onClick={claim} disabled={pending} className="w-full">
          {pending ? "Réclamation…" : "Réclamer la récompense"}
        </Button>
      )}
      {claimed && <p className="m-0 text-center text-xs font-semibold text-green">Récompense réclamée</p>}
      {failed && (
        <p role="alert" className="m-0 text-center text-xs text-muted">
          Hermes n’a pas pu valider la récompense. Réessaie dans un instant.
        </p>
      )}
    </li>
  )
}
