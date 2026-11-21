"use client"

import { useEffect, useRef, useState, type ReactNode } from "react"
import { buttonVariants } from "@/components/ui/button"
import { cn } from "@/lib/cn"

/** Délai pendant lequel le bouton de confirmation ignore toute activation après l'ouverture. */
export const CONFIRM_GUARD_MS = 400

type Props = {
  /** Libellé du bouton initial. */
  children: ReactNode
  /** Question posée avant l'action (« Supprimer définitivement cette image ? »). */
  question: string
  confirmLabel?: string
  onConfirm: () => void | Promise<void>
  disabled?: boolean
  danger?: boolean
  size?: "sm" | "md"
  className?: string
}

/**
 * Action à confirmer dans la page (jamais `window.confirm`) : le premier clic affiche la question et
 * deux boutons ; Échap ou « Annuler » referme, le focus revient au bouton d'origine.
 */
export function ConfirmButton({
  children,
  question,
  confirmLabel = "Confirmer",
  onConfirm,
  disabled,
  danger = true,
  size = "sm",
  className,
}: Props) {
  const [asking, setAsking] = useState(false)
  const trigger = useRef<HTMLButtonElement>(null)
  const cancel = useRef<HTMLButtonElement>(null)
  const wasAsking = useRef(false)
  const openedAt = useRef(0)

  // Focus sur « Annuler », jamais sur l'action : une double frappe d'Entrée (ou l'auto-répétition)
  // sur le bouton d'origine ne doit pas confirmer.
  useEffect(() => {
    if (asking) cancel.current?.focus()
    else if (wasAsking.current) trigger.current?.focus()
    wasAsking.current = asking
  }, [asking])

  if (!asking) {
    return (
      <button
        ref={trigger}
        type="button"
        disabled={disabled}
        onClick={() => {
          openedAt.current = Date.now()
          setAsking(true)
        }}
        className={cn(
          "inline-flex items-center justify-center rounded-[10px] border font-semibold disabled:opacity-50",
          size === "sm" ? "px-3 py-[7px] text-[13px]" : "px-[18px] py-2.5 text-sm",
          danger ? "border-orange/40 text-orange hover:bg-orange/10" : "border-white/14 bg-white/6 text-fg hover:bg-white/10",
          className,
        )}
      >
        {children}
      </button>
    )
  }

  return (
    <span
      role="group"
      aria-label={question}
      className="inline-flex flex-wrap items-center gap-2 rounded-xl border border-orange/40 bg-orange/8 px-3 py-1.5"
      onKeyDown={e => {
        if (e.key === "Escape") setAsking(false)
      }}
    >
      <span className="text-sm text-fg">{question}</span>
      <button
        type="button"
        onClick={async () => {
          // Activation trop proche de l'ouverture (double clic, clavier) : ignorée.
          if (Date.now() - openedAt.current < CONFIRM_GUARD_MS) return
          setAsking(false)
          await onConfirm()
        }}
        className="rounded-[10px] bg-orange px-3 py-[5px] text-[13px] font-bold text-[#1a0c02]"
      >
        {confirmLabel}
      </button>
      <button ref={cancel} type="button" onClick={() => setAsking(false)} className={buttonVariants({ variant: "ghost", size: "sm" })}>
        Annuler
      </button>
    </span>
  )
}
