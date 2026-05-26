'use client'

import { useState, useEffect, useRef, useTransition } from 'react'
import { searchUsers, type UserResult } from './actions'

interface Props {
  selected: UserResult | null
  onSelect: (u: UserResult) => void
  onClear: () => void
  placeholder?: string
  label?: string
}

export function UserSearchInput({
  selected,
  onSelect,
  onClear,
  placeholder = 'Rechercher un pseudo…',
  label = 'Membre Discord',
}: Props) {
  const [query, setQuery]     = useState(selected?.username ?? '')
  const [results, setResults] = useState<UserResult[]>([])
  const [showDrop, setShowDrop] = useState(false)
  const [, startTransition]   = useTransition()
  const dropRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (selected) {
      setQuery(selected.username)
      return
    }
    const id = setTimeout(() => {
      if (query.length >= 2) {
        startTransition(async () => {
          const users = await searchUsers(query)
          setResults(users)
          setShowDrop(true)
        })
      } else {
        setResults([])
        setShowDrop(false)
      }
    }, 300)
    return () => clearTimeout(id)
  }, [query, selected])

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (!dropRef.current?.contains(e.target as Node)) setShowDrop(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const handleSelect = (u: UserResult) => {
    onSelect(u)
    setQuery(u.username)
    setShowDrop(false)
    setResults([])
  }

  const handleClear = () => {
    onClear()
    setQuery('')
    setResults([])
    setShowDrop(false)
  }

  return (
    <div ref={dropRef} className="relative">
      {label && <label className="text-sm text-muted-foreground mb-1 block">{label}</label>}
      <div className="relative">
        <input
          value={query}
          onChange={e => { setQuery(e.target.value); if (selected) onClear() }}
          placeholder={placeholder}
          className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary pr-8"
        />
        {selected && (
          <button
            onClick={handleClear}
            className="absolute right-2 top-2 text-muted-foreground hover:text-foreground text-xs"
          >
            ✕
          </button>
        )}
      </div>

      {showDrop && results.length > 0 && (
        <div className="absolute z-50 top-full mt-1 w-full bg-card border border-border rounded-lg shadow-lg overflow-hidden">
          {results.map(u => (
            <button
              key={u.user_id}
              onClick={() => handleSelect(u)}
              className="w-full flex items-center gap-2 px-3 py-2 hover:bg-accent text-sm text-left"
            >
              {u.discord_avatar ? (
                <img src={u.discord_avatar} alt={u.username} className="w-6 h-6 rounded-full" />
              ) : (
                <div className="w-6 h-6 rounded-full bg-secondary flex items-center justify-center text-xs font-bold">
                  {u.username[0]?.toUpperCase()}
                </div>
              )}
              <span>{u.username}</span>
            </button>
          ))}
        </div>
      )}

      {showDrop && results.length === 0 && query.length >= 2 && (
        <div className="absolute z-50 top-full mt-1 w-full bg-card border border-border rounded-lg shadow-lg px-3 py-2 text-sm text-muted-foreground">
          Aucun membre trouvé
        </div>
      )}
    </div>
  )
}
