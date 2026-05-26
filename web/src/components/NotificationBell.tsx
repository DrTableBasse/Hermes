'use client'
import { useState, useEffect } from 'react'
import { api, Notification } from '@/lib/api'

export default function NotificationBell() {
  const [notifs, setNotifs] = useState<Notification[]>([])
  const [open, setOpen] = useState(false)

  useEffect(() => {
    api.notifications.list().then(r => setNotifs(r.notifications)).catch(() => {})
  }, [])

  const unread = notifs.filter(n => !n.is_read).length

  const handleMarkAll = async () => {
    await api.notifications.markAllRead()
    setNotifs(prev => prev.map(n => ({ ...n, is_read: true })))
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(o => !o)}
        className="relative p-2 rounded-lg hover:bg-accent transition-colors"
        aria-label="Notifications"
      >
        <span className="text-lg">🔔</span>
        {unread > 0 && (
          <span className="absolute -top-1 -right-1 w-5 h-5 flex items-center justify-center bg-destructive text-destructive-foreground text-xs rounded-full font-bold">
            {unread > 9 ? '9+' : unread}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 mt-2 w-80 glass-card shadow-xl z-50">
          <div className="flex items-center justify-between p-3 border-b border-border/60">
            <span className="font-semibold text-sm">Notifications</span>
            {unread > 0 && (
              <button onClick={handleMarkAll} className="text-xs text-primary hover:underline">
                Tout marquer lu
              </button>
            )}
          </div>
          <div className="max-h-80 overflow-y-auto">
            {notifs.length === 0 ? (
              <p className="text-center text-muted-foreground text-sm p-6">Aucune notification</p>
            ) : (
              notifs.slice(0, 20).map(n => (
                <div
                  key={n.id}
                  className={`p-3 border-b border-border/30 transition-opacity ${n.is_read ? 'opacity-50' : ''}`}
                >
                  <p className="text-sm font-medium">{n.title}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">{n.body}</p>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  )
}
