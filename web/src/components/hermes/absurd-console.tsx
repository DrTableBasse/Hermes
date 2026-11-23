"use client"

import { useEffect, useState, useSyncExternalStore } from "react"
import { LOG_TAG_COLORS, pickLogLines, type LogLine } from "@/content/hermes-logs"

const REDUCED = "(prefers-reduced-motion: reduce)"
/** Lignes affichées au chargement, puis fenêtre glissante. */
const INITIAL = 8
const VISIBLE = 11
/** Une ligne toutes les 1,9 s, comme la maquette. */
export const LOG_INTERVAL_MS = 1900

function subscribeReduced(onChange: () => void) {
  const mq = window.matchMedia?.(REDUCED)
  mq?.addEventListener("change", onChange)
  return () => mq?.removeEventListener("change", onChange)
}
const reducedSnapshot = () => window.matchMedia?.(REDUCED).matches ?? false
// Au rendu serveur et à l'hydratation, on suppose le mouvement réduit : rien ne démarre avant de savoir.
const reducedServerSnapshot = () => true

const clock = new Intl.DateTimeFormat("fr-FR", {
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hourCycle: "h23",
  timeZone: "Europe/Paris",
})

type Entry = { id: number; at: number; line: LogLine }

function initialEntries(sequence: LogLine[], startedAt: number): Entry[] {
  return sequence.slice(0, INITIAL).map((line, i) => ({
    id: i,
    at: startedAt - (INITIAL - 1 - i) * LOG_INTERVAL_MS,
    line,
  }))
}

type AbsurdConsoleProps = {
  /** Graine de l'ordre des lignes, fixée côté serveur (même rendu à l'hydratation). */
  seed: number
  /** Heure du rendu serveur (ms) : horodatage des lignes initiales. */
  startedAt: number
}

/**
 * Journal d'activité d'Hermes, inventé et assumé comme tel. Une ligne s'ajoute toutes les 1,9 s ;
 * survol ou focus mettent en pause (WCAG 2.2.2) ; sous mouvement réduit, le journal reste figé.
 */
export function AbsurdConsole({ seed, startedAt }: AbsurdConsoleProps) {
  const [sequence] = useState(() => pickLogLines(seed, Number.MAX_SAFE_INTEGER))
  const [entries, setEntries] = useState(() => initialEntries(sequence, startedAt))
  const [paused, setPaused] = useState(false)
  const reduced = useSyncExternalStore(subscribeReduced, reducedSnapshot, reducedServerSnapshot)

  useEffect(() => {
    if (reduced || paused) return
    const id = window.setInterval(() => {
      setEntries(prev => {
        const next = prev[prev.length - 1].id + 1
        const entry = { id: next, at: Date.now(), line: sequence[next % sequence.length] }
        return [...prev, entry].slice(-VISIBLE)
      })
    }, LOG_INTERVAL_MS)
    return () => window.clearInterval(id)
  }, [reduced, paused, sequence])

  return (
    <section
      className="grid min-h-[330px] grid-rows-[auto_1fr] overflow-hidden rounded-2xl border border-cyan/20 bg-[#070912]"
      aria-label="Journal d’activité d’Hermes (pour rire)"
      // Focusable : le focus clavier met le défilé en pause, comme le survol.
      tabIndex={0}
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocus={() => setPaused(true)}
      onBlur={() => setPaused(false)}
      data-testid="hermes-console"
      data-paused={paused || reduced ? "true" : undefined}
    >
      <div className="flex items-center gap-2 border-b border-white/6 bg-[#0D1020] px-3.5 py-2.5 text-xs text-muted" aria-hidden="true">
        <i className="size-2.5 rounded-full bg-[#FF6B6B]" />
        <i className="size-2.5 rounded-full bg-[#FFC84A]" />
        <i className="size-2.5 rounded-full bg-[#3BD16F]" />
        <span className="ml-2">hermes@saucisseland : journal en direct (pour rire)</span>
      </div>
      <div className="flex h-[290px] flex-col justify-end overflow-hidden px-4 py-3.5 font-mono text-[13px] leading-[1.65] text-[#C8D3E6]">
        <ol className="m-0 list-none p-0">
          {entries.map(e => (
            <li key={e.id} className="overflow-hidden text-ellipsis whitespace-nowrap motion-safe:animate-log-in">
              <time className="text-[#7C86A8]">[{clock.format(e.at)}]</time>{" "}
              <span className="font-bold" style={{ color: LOG_TAG_COLORS[e.line.tag] }}>
                {e.line.tag}
              </span>{" "}
              {e.line.text}
            </li>
          ))}
        </ol>
        <div aria-hidden="true">
          &gt; <span className="inline-block h-[15px] w-2 bg-cyan align-[-2px] motion-safe:animate-blink" />
        </div>
      </div>
    </section>
  )
}
