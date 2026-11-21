"use client"

import { usePathname, useRouter, useSearchParams } from "next/navigation"
import { useEffect, useRef, useState } from "react"

const DELAY_MS = 350

/** Recherche d'un membre : met `?q=` à jour après une courte pause et revient à la page 1. */
export function RankSearch({ defaultValue = "" }: { defaultValue?: string }) {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const [value, setValue] = useState(defaultValue)
  // Dernière valeur déjà portée par l'URL : évite de naviguer au montage ou après un simple retour arrière.
  const applied = useRef(defaultValue.trim())

  useEffect(() => {
    const text = value.trim()
    if (text === applied.current) return
    const id = setTimeout(() => {
      const params = new URLSearchParams(searchParams.toString())
      if (text) params.set("q", text)
      else params.delete("q")
      params.delete("page")
      applied.current = text
      router.push(`${pathname}?${params}`)
    }, DELAY_MS)
    return () => clearTimeout(id)
  }, [value, pathname, router, searchParams])

  return (
    <div className="relative w-full max-w-xs">
      <input
        type="search"
        value={value}
        onChange={e => setValue(e.target.value)}
        placeholder="Rechercher un membre…"
        aria-label="Rechercher un membre"
        className="w-full rounded-xl border border-line bg-[rgb(19_22_42/0.9)] px-4 py-2.5 text-sm text-fg placeholder:text-muted focus:border-violet/60 focus:outline-none"
      />
    </div>
  )
}
