'use client'
import { useState } from 'react'
import Link from 'next/link'
import { api } from '@/lib/api'
import type { Ticket } from '@/lib/api'

const STATUS_LABEL: Record<string, string> = {
  open:     '🟢 Ouvert',
  resolved: '🟡 Résolu',
  closed:   '⚪ Fermé',
}

export default function TicketSection({
  initialTickets,
  locale,
}: {
  initialTickets: Ticket[]
  locale: string
}) {
  const [tickets, setTickets]  = useState<Ticket[]>(initialTickets)
  const [title, setTitle]      = useState('')
  const [creating, setCreating] = useState(false)
  const [error, setError]      = useState<string | null>(null)

  const openTicket = tickets.find((t) => t.status === 'open')

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    if (!title.trim() || creating) return
    setCreating(true)
    setError(null)
    try {
      const ticket = await api.tickets.create(title.trim())
      setTickets((prev) => [ticket, ...prev])
      setTitle('')
    } catch (err: any) {
      setError(err.message ?? 'Erreur lors de la création')
    } finally {
      setCreating(false)
    }
  }

  return (
    <section>
      <h2 className="text-xl font-bold mb-5">🎫 Tickets</h2>

      {/* Create form — only if no open ticket */}
      {!openTicket && (
        <form onSubmit={handleCreate} className="glass-card p-4 mb-4 flex gap-2">
          <input
            className="flex-1 rounded-md border border-border bg-background px-3 py-2 text-sm"
            placeholder="Décrivez votre problème en quelques mots..."
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            disabled={creating}
          />
          <button
            type="submit"
            disabled={creating || !title.trim()}
            className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
          >
            {creating ? '...' : 'Ouvrir un ticket'}
          </button>
        </form>
      )}

      {error && <p className="text-red-400 text-sm mb-3">{error}</p>}

      {/* Ticket list */}
      {tickets.length === 0 ? (
        <p className="text-muted-foreground text-sm">Aucun ticket pour le moment.</p>
      ) : (
        <div className="space-y-2">
          {tickets.map((t) => (
            <Link
              key={t.id}
              href={`/${locale}/tickets/${t.id}`}
              className="glass-card p-3 flex items-center gap-3 hover:bg-accent/40 transition-colors block"
            >
              <span className="text-sm text-muted-foreground w-8 shrink-0">#{t.id}</span>
              <span className="flex-1 text-sm font-medium truncate">{t.title}</span>
              <span className="text-xs shrink-0">{STATUS_LABEL[t.status]}</span>
            </Link>
          ))}
        </div>
      )}
    </section>
  )
}
