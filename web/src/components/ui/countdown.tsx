"use client"

import { useSyncExternalStore } from "react"
import { cn } from "@/lib/cn"
import { formatCountdown } from "@/lib/format"

const REDUCED = "(prefers-reduced-motion: reduce)"

function reducedMotion() {
  return typeof window !== "undefined" && window.matchMedia?.(REDUCED).matches
}

// Horloge partagée : seconde courante, ou minute courante sous mouvement réduit (le décompte ne
// « défile » plus chaque seconde). Valeur primitive, donc stable entre deux lectures.
function subscribe(onTick: () => void) {
  const id = window.setInterval(onTick, 1000)
  return () => window.clearInterval(id)
}
function snapshot() {
  const s = Math.floor(Date.now() / 1000)
  return reducedMotion() ? s - (s % 60) : s
}
function serverSnapshot() {
  return null
}

const pad = (n: number) => String(n).padStart(2, "0")

type CountdownProps = {
  /** Date ISO de début. */
  target: string
  /** Texte affiché une fois l'heure passée. */
  doneLabel?: string
  className?: string
}

export function Countdown({ target, doneLabel = "C'est parti", className }: CountdownProps) {
  const nowSeconds = useSyncExternalStore(subscribe, snapshot, serverSnapshot)
  const reduced = nowSeconds !== null && reducedMotion()
  const t = nowSeconds === null ? null : formatCountdown(new Date(target), new Date(nowSeconds * 1000))

  if (t?.past) {
    return <p className={cn("font-display text-2xl font-bold text-cyan", className)}>{doneLabel}</p>
  }

  const units: Array<[number | undefined, string]> = [
    ...(t && t.days > 0 ? [[t.days, t.days > 1 ? "jours" : "jour"] as [number, string]] : []),
    [t?.hours, "heures"],
    [t?.minutes, "minutes"],
    ...(reduced ? [] : [[t?.seconds, "secondes"] as [number | undefined, string]]),
  ]

  return (
    <div
      role="timer"
      aria-label={
        t ? `Début dans ${t.days ? `${t.days} j ` : ""}${t.hours} h ${t.minutes} min` : "Compte à rebours"
      }
      className={cn("flex gap-2.5", className)}
    >
      {units.map(([value, label]) => (
        <div
          key={label}
          aria-hidden="true"
          className="min-w-[84px] rounded-[14px] border border-white/10 bg-[rgb(12_14_26/0.6)] px-2.5 py-3 text-center"
        >
          <b className="block font-display text-[38px] leading-none tabular-nums">
            {value === undefined ? "--" : pad(value)}
          </b>
          <span className="text-xs text-muted">{label}</span>
        </div>
      ))}
    </div>
  )
}
