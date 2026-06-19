'use client'
import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { api } from '@/lib/api'

export default function AdminTicketPanel({ locale }: { locale: string }) {
  const router = useRouter()
  const [userId, setUserId] = useState('')
  const [title, setTitle]   = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError]   = useState<string | null>(null)

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    if (!userId.trim() || !title.trim() || loading) return
    setLoading(true)
    setError(null)
    try {
      const ticket = await api.tickets.adminCreate(userId.trim(), title.trim())
      router.push(`/${locale}/tickets/${ticket.id}`)
    } catch (err: any) {
      setError(err.message ?? 'Erreur')
      setLoading(false)
    }
  }

  return (
    <div className="glass-card p-5 mb-8">
      <h2 className="font-semibold text-sm text-muted-foreground mb-3 uppercase tracking-wide">
        Créer un ticket pour un utilisateur
      </h2>
      <form onSubmit={handleCreate} className="flex flex-col gap-3 sm:flex-row sm:items-end">
        <div className="flex-1">
          <label className="text-xs text-muted-foreground mb-1 block">Discord ID</label>
          <input
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            placeholder="ex: 279205522970902528"
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
            disabled={loading}
          />
        </div>
        <div className="flex-[2]">
          <label className="text-xs text-muted-foreground mb-1 block">Sujet</label>
          <input
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            placeholder="Décrivez le problème..."
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            disabled={loading}
          />
        </div>
        <button
          type="submit"
          disabled={loading || !userId.trim() || !title.trim()}
          className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50 shrink-0"
        >
          {loading ? '...' : 'Créer'}
        </button>
      </form>
      {error && <p className="text-red-400 text-xs mt-2">{error}</p>}
    </div>
  )
}
