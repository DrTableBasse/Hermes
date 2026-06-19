'use client'
import { useState } from 'react'
import { api } from '@/lib/api'
import type { TicketDetail, TicketMessage } from '@/lib/api'

function SourceBadge({ source }: { source: 'web' | 'discord' }) {
  return (
    <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${
      source === 'discord'
        ? 'bg-indigo-500/20 text-indigo-300'
        : 'bg-emerald-500/20 text-emerald-300'
    }`}>
      {source === 'discord' ? '🎮 Discord' : '🌐 Web'}
    </span>
  )
}

export default function TicketChat({
  ticket,
  isAdmin,
  locale,
}: {
  ticket: TicketDetail
  isAdmin: boolean
  locale: string
}) {
  const [messages, setMessages] = useState<TicketMessage[]>(ticket.messages)
  const [content, setContent]   = useState('')
  const [sending, setSending]   = useState(false)
  const [status, setStatus]     = useState(ticket.status)
  const [error, setError]       = useState<string | null>(null)

  const isClosed = status !== 'open'

  async function sendMessage(e: React.FormEvent) {
    e.preventDefault()
    if (!content.trim() || sending) return
    setSending(true)
    setError(null)
    try {
      await api.tickets.message(ticket.id, content.trim())
      // Optimistic: reload messages from server
      const updated = await api.tickets.get(ticket.id)
      setMessages(updated.messages)
      setContent('')
    } catch (err: any) {
      setError(err.message ?? 'Erreur lors de l\'envoi')
    } finally {
      setSending(false)
    }
  }

  async function handleResolve() {
    try {
      await api.tickets.resolve(ticket.id)
      setStatus('resolved')
    } catch (err: any) {
      setError(err.message)
    }
  }

  async function handleClose() {
    try {
      await api.tickets.close(ticket.id)
      setStatus('closed')
    } catch (err: any) {
      setError(err.message)
    }
  }

  return (
    <div className="space-y-4">
      {/* Message thread */}
      <div className="space-y-3 max-h-[60vh] overflow-y-auto">
        {messages.length === 0 && (
          <p className="text-muted-foreground text-center py-6">Aucun message pour l&apos;instant.</p>
        )}
        {messages.map((m) => (
          <div key={m.id} className="glass-card p-4">
            <div className="flex items-center gap-2 mb-1">
              <span className="font-semibold text-sm">{m.author_name}</span>
              <SourceBadge source={m.source} />
              <span className="text-xs text-muted-foreground ml-auto">
                {new Date(m.created_at).toLocaleString('fr-FR')}
              </span>
            </div>
            <p className="text-sm whitespace-pre-wrap">{m.content}</p>
          </div>
        ))}
      </div>

      {/* Error */}
      {error && <p className="text-red-400 text-sm">{error}</p>}

      {/* Reply form */}
      {!isClosed && (
        <form onSubmit={sendMessage} className="flex gap-2">
          <input
            className="flex-1 rounded-md border border-border bg-background px-3 py-2 text-sm"
            placeholder="Votre message..."
            value={content}
            onChange={(e) => setContent(e.target.value)}
            disabled={sending}
          />
          <button
            type="submit"
            disabled={sending || !content.trim()}
            className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
          >
            {sending ? '...' : 'Envoyer'}
          </button>
        </form>
      )}

      {/* Actions */}
      <div className="flex gap-3 pt-2">
        {!isClosed && !isAdmin && (
          <button
            onClick={handleResolve}
            className="rounded-md border border-yellow-500/50 px-4 py-2 text-sm text-yellow-400 hover:bg-yellow-500/10"
          >
            ✅ Marquer comme résolu
          </button>
        )}
        {!isClosed && isAdmin && (
          <button
            onClick={handleClose}
            className="rounded-md border border-red-500/50 px-4 py-2 text-sm text-red-400 hover:bg-red-500/10"
          >
            🔒 Fermer définitivement
          </button>
        )}
        {isClosed && (
          <p className="text-muted-foreground text-sm">
            Ce ticket est {status === 'resolved' ? 'résolu' : 'fermé'}.
          </p>
        )}
      </div>
    </div>
  )
}
