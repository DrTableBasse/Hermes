'use client'

import { useState, useEffect } from 'react'
import { useRouter, usePathname, useSearchParams } from 'next/navigation'

export function SearchBar({ defaultValue = '' }: { defaultValue?: string }) {
  const router       = useRouter()
  const pathname     = usePathname()
  const searchParams = useSearchParams()
  const [value, setValue] = useState(defaultValue)

  useEffect(() => {
    const id = setTimeout(() => {
      const params = new URLSearchParams(searchParams.toString())
      if (value.trim()) {
        params.set('q', value.trim())
      } else {
        params.delete('q')
      }
      params.delete('page')
      router.push(`${pathname}?${params}`)
    }, 350)
    return () => clearTimeout(id)
  }, [value])

  return (
    <div className="relative">
      <svg
        className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground pointer-events-none"
        fill="none" stroke="currentColor" viewBox="0 0 24 24"
      >
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M21 21l-4.35-4.35M17 11A6 6 0 111 11a6 6 0 0116 0z" />
      </svg>
      <input
        value={value}
        onChange={e => setValue(e.target.value)}
        placeholder="Rechercher un article…"
        className="pl-9 pr-4 py-2 bg-card border border-border rounded-lg text-sm w-full max-w-xs focus:outline-none focus:ring-2 focus:ring-primary"
      />
      {value && (
        <button
          onClick={() => setValue('')}
          className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground text-xs"
        >✕</button>
      )}
    </div>
  )
}
