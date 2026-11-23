"use client"

import { Bell } from "lucide-react"
import { useCallback, useEffect, useId, useRef, useState } from "react"
import { api } from "@/lib/api/client"
import type { Notification } from "@/lib/api/types"
import { formatAgo } from "@/lib/format"

const SHOWN = 20

/** Cloche des notifications du membre connecté (`/notifications`, session requise). */
export function NotificationBell() {
  const [notifs, setNotifs] = useState<Notification[]>([])
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const panelId = useId()
  const close = useCallback(() => setOpen(false), [])

  useEffect(() => {
    let alive = true
    api.notifications
      .list()
      .then(r => alive && setNotifs(r.notifications))
      .catch(() => {})
    return () => {
      alive = false
    }
  }, [])

  // Échap ferme et rend le focus au déclencheur ; un clic hors du panneau ferme.
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return
      close()
      triggerRef.current?.focus()
    }
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) close()
    }
    document.addEventListener("keydown", onKey)
    document.addEventListener("mousedown", onClick)
    return () => {
      document.removeEventListener("keydown", onKey)
      document.removeEventListener("mousedown", onClick)
    }
  }, [open, close])

  const unread = notifs.filter(n => !n.is_read).length

  async function markAll() {
    try {
      await api.notifications.markAllRead()
      setNotifs(prev => prev.map(n => ({ ...n, is_read: true })))
    } catch {
      // Échec : rien n'est marqué lu côté serveur, l'affichage ne doit pas mentir.
    }
  }

  const now = new Date()
  return (
    <div ref={ref} className="relative">
      <button
        ref={triggerRef}
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        aria-label={unread > 0 ? `Notifications, ${unread} non lue${unread > 1 ? "s" : ""}` : "Notifications"}
        onClick={() => setOpen(o => !o)}
        className="relative grid size-10 place-items-center rounded-xl hover:bg-white/6"
      >
        <Bell className="size-5" aria-hidden="true" />
        {unread > 0 && (
          <span
            aria-hidden="true"
            className="absolute -top-0.5 -right-0.5 grid min-w-5 place-items-center rounded-full bg-violet-deep px-1 text-xs font-bold text-white"
          >
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>
      {open && (
        <div
          id={panelId}
          className="absolute top-[calc(100%+10px)] right-0 z-50 w-80 max-w-[calc(100vw-2rem)] rounded-2xl border border-white/10 bg-panel-2 shadow-[0_24px_50px_rgb(0_0_0/0.5)]"
        >
          <div className="flex items-center justify-between border-b border-line p-3">
            <span className="text-sm font-semibold">Notifications</span>
            {unread > 0 && (
              <button type="button" onClick={markAll} className="text-xs font-semibold text-cyan hover:underline">
                Tout marquer lu
              </button>
            )}
          </div>
          <div className="max-h-80 overflow-y-auto">
            {notifs.length === 0 ? (
              <p className="m-0 p-6 text-center text-sm text-muted">Aucune notification</p>
            ) : (
              <ul className="m-0 list-none p-0">
                {notifs.slice(0, SHOWN).map(n => (
                  <li key={n.id} className={n.is_read ? "border-b border-line/60 p-3 opacity-60" : "border-b border-line/60 p-3"}>
                    <p className="m-0 text-sm font-medium">{n.title}</p>
                    {n.body && <p className="m-0 mt-0.5 text-xs text-muted">{n.body}</p>}
                    <p className="m-0 mt-1 text-xs text-muted/80">{formatAgo(n.created_at, now)}</p>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
