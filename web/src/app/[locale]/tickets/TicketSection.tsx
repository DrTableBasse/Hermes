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
const STATUS_CLASS: Record<string, string> = {
  open:     'text-green-400',
  resolved: 'text-yellow-400',
  closed:   'text-muted-foreground',
}

function TicketRow({ t, locale }: { t: Ticket; locale: string }) {
  return (
    <Link
      href={`/${locale}/tickets/${t.id}`}
      className="glass-card p-4 flex items-center gap-4 hover:bg-accent/40 transition-colors block"
    >
      <span className="text-sm text-muted-foreground w-8 shrink-0">#{t.id}</span>
      <div className="flex-1 min-w-0">
        <p className="font-medium truncate">{t.title}</p>
        <p className="text-xs text-muted-foreground mt-0.5">
          {new Date(t.created_at).toLocaleDateString('fr-FR')}
          {t.closed_at && ` · fermé le ${new Date(t.closed_at).toLocaleDateString('fr-FR')}`}
        </p>
      </div>
      <span className={`text-sm font-medium shrink-0 ${STATUS_CLASS[t.status]}`}>
        {STATUS_LABEL[t.status]}
      </span>
    </Link>
  )
}

export default function TicketSection({
  initialTickets,
  locale,
}: {
  initialTickets: Ticket[]
  locale: string
}) {
  const [tickets, setTickets]   = useState<Ticket[]>(initialTickets)
  const [title, setTitle]       = useState('')
  const [creating, setCreating] = useState(false)
  const [error, setError]       = useState<string | null>(null)

  const openTicket  = tickets.find((t) => t.status === 'open')
  const pastTickets = tickets.filter((t) => t.status !== 'open')

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
    <div className="space-y-10">
      {/* ── Ticket actif ── */}
      <section>
        <h2 className="text-lg font-bold mb-4">Ticket en cours</h2>

        {openTicket ? (
          <TicketRow t={openTicket} locale={locale} />
        ) : (
          <>
            <p className="text-muted-foreground text-sm mb-4">
              Vous n&apos;avez pas de ticket ouvert.
            </p>
            <form onSubmit={handleCreate} className="glass-card p-4 flex gap-2">
              <input
                className="flex-1 rounded-md border border-border bg-background px-3 py-2 text-sm"
                placeholder="Décrivez votre problème en quelques mots…"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                disabled={creating}
              />
              <button
                type="submit"
                disabled={creating || !title.trim()}
                className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
              >
                {creating ? '…' : 'Ouvrir un ticket'}
              </button>
            </form>
          </>
        )}

        {error && <p className="text-red-400 text-sm mt-2">{error}</p>}
      </section>

      {/* ── Historique ── */}
      {pastTickets.length > 0 && (
        <section>
          <h2 className="text-lg font-bold mb-4">Historique</h2>
          <div className="space-y-2">
            {pastTickets.map((t) => (
              <TicketRow key={t.id} t={t} locale={locale} />
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
