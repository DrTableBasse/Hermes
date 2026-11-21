"use client"

import { useId, useState } from "react"
import { Button } from "@/components/ui/button"
import { Panel } from "@/components/ui/panel"
import { api } from "@/lib/api/client"
import type { UserSearchResult } from "@/lib/api/types"
import { cn } from "@/lib/cn"
import { ConfirmButton } from "./confirm-button"
import { adminErrorText, FIELD, LABEL, type Feedback } from "./form"
import { UserSearchInput } from "./user-search-input"

type Action = "warn" | "timeout" | "kick" | "ban"

const LABELS: Record<Action, { button: string; done: string; question: (name: string) => string }> = {
  warn: { button: "Avertir", done: "Avertissement enregistré", question: n => `Avertir ${n} ?` },
  timeout: { button: "Exclure temporairement", done: "Exclusion temporaire appliquée", question: n => `Exclure ${n} temporairement ?` },
  kick: { button: "Expulser", done: "Membre expulsé", question: n => `Expulser ${n} du serveur ?` },
  ban: { button: "Bannir", done: "Membre banni", question: n => `Bannir ${n} définitivement ?` },
}

const DEFAULT_REASON = "Action depuis le site"

type Props = {
  target: UserSearchResult | null
  onTarget: (user: UserSearchResult | null) => void
  /** Appelé après une sanction réussie (rafraîchir la fiche et la liste). */
  onDone: () => void
}

/** Sanctions : avertissement direct ; exclusion, expulsion et bannissement après confirmation. */
export function ModerationActions({ target, onTarget, onDone }: Props) {
  const ids = useId()
  const [reason, setReason] = useState("")
  const [duration, setDuration] = useState("60")
  const [busy, setBusy] = useState(false)
  const [feedback, setFeedback] = useState<Feedback>(null)

  const minutes = Number(duration)
  const durationError =
    Number.isInteger(minutes) && minutes >= 1 && minutes <= 40320 ? null : "Durée en minutes, de 1 à 40 320 (28 jours)."

  async function act(action: Action) {
    if (!target) return
    setBusy(true)
    setFeedback(null)
    const body = { user_id: target.user_id, reason: reason.trim() || DEFAULT_REASON }
    try {
      if (action === "warn") await api.admin.warn(body)
      else if (action === "timeout") await api.admin.timeout({ ...body, duration: minutes })
      else if (action === "kick") await api.admin.kick(body)
      else await api.admin.ban(body)
      setFeedback({ kind: "ok", text: `${LABELS[action].done} : ${target.username}.` })
      setReason("")
      onDone()
    } catch (e) {
      setFeedback({ kind: "error", text: adminErrorText(e) })
    } finally {
      setBusy(false)
    }
  }

  const disabled = !target || busy
  const name = target?.username ?? ""

  return (
    <Panel as="section" aria-labelledby={`${ids}-title`} className="grid gap-5">
      <h2 id={`${ids}-title`} className="m-0 font-display text-xl font-extrabold">
        Sanctionner un membre
      </h2>
      <div className="grid gap-4 md:grid-cols-[1.2fr_1.5fr_0.7fr]">
        <UserSearchInput
          selected={target}
          onSelect={u => {
            onTarget(u)
            setFeedback(null)
          }}
          onClear={() => onTarget(null)}
        />
        <div className="grid gap-1.5">
          <label htmlFor={`${ids}-reason`} className={LABEL}>
            Raison
          </label>
          <input
            id={`${ids}-reason`}
            value={reason}
            maxLength={500}
            onChange={e => setReason(e.target.value)}
            placeholder={DEFAULT_REASON}
            className={FIELD}
          />
        </div>
        <div className="grid gap-1.5">
          <label htmlFor={`${ids}-duration`} className={LABEL}>
            Durée (min)
          </label>
          <input
            id={`${ids}-duration`}
            inputMode="numeric"
            value={duration}
            onChange={e => setDuration(e.target.value)}
            aria-invalid={durationError !== null}
            aria-describedby={`${ids}-duration-help`}
            className={FIELD}
          />
          <span id={`${ids}-duration-help`} className={cn("text-xs", durationError ? "text-orange" : "text-muted")}>
            {durationError ?? "Pour l’exclusion temporaire."}
          </span>
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <Button size="sm" variant="ghost" disabled={disabled} onClick={() => void act("warn")}>
          {LABELS.warn.button}
        </Button>
        <ConfirmButton question={LABELS.timeout.question(name)} disabled={disabled || durationError !== null} onConfirm={() => act("timeout")}>
          {LABELS.timeout.button}
        </ConfirmButton>
        <ConfirmButton question={LABELS.kick.question(name)} disabled={disabled} onConfirm={() => act("kick")}>
          {LABELS.kick.button}
        </ConfirmButton>
        <ConfirmButton question={LABELS.ban.question(name)} confirmLabel="Bannir" disabled={disabled} onConfirm={() => act("ban")}>
          {LABELS.ban.button}
        </ConfirmButton>
      </div>
      {feedback && (
        <p role={feedback.kind === "error" ? "alert" : "status"} className={cn("m-0 text-sm", feedback.kind === "error" ? "text-orange" : "text-green")}>
          {feedback.text}
        </p>
      )}
    </Panel>
  )
}
