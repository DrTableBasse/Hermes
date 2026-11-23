"use client"

import { X } from "lucide-react"
import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react"
import { Avatar } from "@/components/ui/avatar"
import { api } from "@/lib/api/client"
import type { UserSearchResult } from "@/lib/api/types"
import { cn } from "@/lib/cn"
import { FIELD, LABEL } from "./form"

/** Délai après la dernière frappe avant d'interroger `/admin/users/search`. */
export const SEARCH_DEBOUNCE_MS = 300
const MIN_CHARS = 2

type Props = {
  selected: UserSearchResult | null
  onSelect: (user: UserSearchResult) => void
  onClear: () => void
  label?: string
  placeholder?: string
}

type Results = { status: "idle" } | { status: "ok"; users: UserSearchResult[] } | { status: "error" }

/**
 * Recherche d'un membre par pseudo (combobox ARIA) : requête après une pause de frappe, flèches pour
 * parcourir, Entrée pour choisir, Échap pour fermer. Une réponse arrivée après une frappe plus récente
 * est ignorée.
 */
export function UserSearchInput({
  selected,
  onSelect,
  onClear,
  label = "Membre Discord",
  placeholder = "Rechercher un pseudo…",
}: Props) {
  const ids = useId()
  const [text, setText] = useState(selected?.username ?? "")
  const [results, setResults] = useState<Results>({ status: "idle" })
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(-1)
  const latest = useRef(0)
  // Membre choisi ailleurs (bouton « Sanctionner » d'une fiche) : son pseudo remplace la saisie.
  const [shown, setShown] = useState(selected)
  if (selected !== shown) {
    setShown(selected)
    if (selected) setText(selected.username)
  }

  const q = text.trim()
  const searchable = !selected && q.length >= MIN_CHARS

  useEffect(() => {
    if (!searchable) return
    const timer = setTimeout(async () => {
      const call = ++latest.current
      let next: Results
      try {
        next = { status: "ok", users: (await api.admin.searchUsers(q)).users }
      } catch {
        next = { status: "error" }
      }
      if (call !== latest.current) return
      setResults(next)
      setActive(-1)
      setOpen(true)
    }, SEARCH_DEBOUNCE_MS)
    return () => clearTimeout(timer)
  }, [q, searchable])

  const users = searchable && results.status === "ok" ? results.users : []
  const listId = `${ids}-list`
  const optionId = (i: number) => `${ids}-opt-${i}`
  const showList = open && users.length > 0

  function choose(user: UserSearchResult) {
    onSelect(user)
    setText(user.username)
    setOpen(false)
    setActive(-1)
  }

  function onKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown" && users.length > 0) {
      e.preventDefault()
      setOpen(true)
      setActive(i => Math.min(i + 1, users.length - 1))
    } else if (e.key === "ArrowUp" && users.length > 0) {
      e.preventDefault()
      setActive(i => Math.max(i - 1, 0))
    } else if (e.key === "Enter" && showList && active >= 0) {
      e.preventDefault()
      choose(users[active])
    } else if (e.key === "Escape") {
      setOpen(false)
      setActive(-1)
    }
  }

  return (
    <div className="relative grid gap-1.5">
      <label htmlFor={`${ids}-input`} className={LABEL}>
        {label}
      </label>
      <div className="relative">
        <input
          id={`${ids}-input`}
          role="combobox"
          aria-expanded={showList}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={showList && active >= 0 ? optionId(active) : undefined}
          autoComplete="off"
          value={text}
          placeholder={placeholder}
          onChange={e => {
            setText(e.target.value)
            // Saisie trop courte : toute réponse encore en route est périmée.
            if (e.target.value.trim().length < MIN_CHARS) {
              latest.current += 1
              setOpen(false)
            }
            if (selected) onClear()
          }}
          onKeyDown={onKeyDown}
          onBlur={() => setOpen(false)}
          className={cn(FIELD, selected && "pr-10")}
        />
        {selected && (
          <button
            type="button"
            onClick={() => {
              onClear()
              setText("")
              setResults({ status: "idle" })
            }}
            aria-label={`Effacer ${selected.username}`}
            className="absolute top-1/2 right-2 grid size-7 -translate-y-1/2 place-items-center rounded-lg text-muted hover:text-fg"
          >
            <X className="size-4" aria-hidden="true" />
          </button>
        )}
      </div>
      {showList && (
        <ul
          id={listId}
          role="listbox"
          aria-label={label}
          className="absolute top-full z-30 m-0 mt-1 grid w-full list-none gap-0.5 rounded-xl border border-line bg-panel-2 p-1 shadow-[0_16px_30px_rgb(0_0_0/0.45)]"
        >
          {users.map((u, i) => (
            <li
              key={u.user_id}
              id={optionId(i)}
              role="option"
              aria-selected={i === active}
              // mousedown : choisi avant que le blur de l'input ne ferme la liste.
              onMouseDown={e => {
                e.preventDefault()
                choose(u)
              }}
              className={cn(
                "flex cursor-pointer items-center gap-2.5 rounded-lg px-3 py-2 text-sm",
                i === active ? "bg-violet/15 text-fg" : "text-msg hover:bg-white/6",
              )}
            >
              <Avatar name={u.username} src={u.discord_avatar} size={24} />
              {u.username}
            </li>
          ))}
        </ul>
      )}
      {open && searchable && results.status === "ok" && users.length === 0 && (
        <p role="status" className="m-0 text-sm text-muted">
          Aucun membre trouvé
        </p>
      )}
      {searchable && results.status === "error" && (
        <p role="alert" className="m-0 text-sm text-orange">
          Recherche impossible : le site ne répond pas. Réessaie dans un moment.
        </p>
      )}
    </div>
  )
}
