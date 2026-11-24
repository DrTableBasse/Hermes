"use client"

import Link from "next/link"
import { useId, useRef, useState, type KeyboardEvent, type ReactNode } from "react"
import { cn } from "@/lib/cn"

type Tab = { key: string; label: string; panel: ReactNode }

/**
 * Onglets ARIA (tablist/tab/tabpanel) : flèches gauche/droite, Début/Fin ; tabindex itinérant.
 * Tous les panneaux restent rendus (masqués par `hidden`) : chaque `aria-controls` vise un élément présent.
 * `siteHref` : lien vers l'onglet « Site », hors de la liste d'onglets (autre page).
 */
export function PermissionsTabs({ tabs, siteHref }: { tabs: Tab[]; siteHref: string }) {
  const base = useId()
  const [active, setActive] = useState(0)
  const refs = useRef<(HTMLButtonElement | null)[]>([])

  function onKeyDown(e: KeyboardEvent<HTMLButtonElement>, index: number) {
    const last = tabs.length - 1
    const next =
      e.key === "ArrowRight" ? (index === last ? 0 : index + 1)
      : e.key === "ArrowLeft" ? (index === 0 ? last : index - 1)
      : e.key === "Home" ? 0
      : e.key === "End" ? last
      : null
    if (next === null) return
    e.preventDefault()
    setActive(next)
    refs.current[next]?.focus()
  }

  return (
    <div className="grid gap-6">
      <div className="flex flex-wrap items-center gap-3">
        <div role="tablist" aria-label="Permissions" className="flex flex-wrap gap-1.5">
          {tabs.map((t, i) => (
            <button
              key={t.key}
              ref={el => {
                refs.current[i] = el
              }}
              type="button"
              role="tab"
              id={`${base}-tab-${t.key}`}
              aria-selected={i === active}
              aria-controls={`${base}-panel-${t.key}`}
              tabIndex={i === active ? 0 : -1}
              onClick={() => setActive(i)}
              onKeyDown={e => onKeyDown(e, i)}
              className={cn(
                "rounded-full border px-4 py-1.5 text-sm font-semibold",
                i === active
                  ? "border-violet bg-violet/10 text-violet"
                  : "border-line text-muted hover:border-violet/40 hover:text-fg",
              )}
            >
              {t.label}
            </button>
          ))}
        </div>
        <Link
          href={siteHref}
          prefetch={false}
          className="rounded-full border border-dashed border-line px-4 py-1.5 text-sm font-semibold text-muted hover:text-fg"
        >
          Site → Accès
        </Link>
      </div>
      {tabs.map((t, i) => (
        <div
          key={t.key}
          role="tabpanel"
          id={`${base}-panel-${t.key}`}
          aria-labelledby={`${base}-tab-${t.key}`}
          hidden={i !== active}
          tabIndex={0}
          className="grid gap-6"
        >
          {t.panel}
        </div>
      ))}
    </div>
  )
}
