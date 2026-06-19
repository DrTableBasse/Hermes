'use client'
import { useState, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { api } from '@/lib/api'

export default function AdminTicketPanel({ locale }: { locale: string }) {
  const router = useRouter()
  const [userId, setUserId]     = useState('')
  const [title, setTitle]       = useState('')
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState<string | null>(null)
  const [preview, setPreview]   = useState<string | null>(null)
  const [resolving, setResolving] = useState(false)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  function handleUserIdChange(e: React.ChangeEvent<HTMLInputElement>) {
    const val = e.target.value
    setUserId(val)
    setPreview(null)
    setError(null)

    if (debounceRef.current) clearTimeout(debounceRef.current)

    const trimmed = val.trim()
    if (!/^\d{15,20}$/.test(trimmed)) return

    debounceRef.current = setTimeout(async () => {
      setResolving(true)
      try {
        const data = await api.users.publicStats(trimmed)
        const name = (data as any).nickname || (data as any).username
        setPreview(name ?? null)
      } catch {
        setPreview(null)
      } finally {
        setResolving(false)
      }
    }, 400)
  }

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
            onChange={handleUserIdChange}
            disabled={loading}
          />
          <div className="mt-1 h-4">
            {resolving && (
              <span className="text-xs text-muted-foreground">Recherche…</span>
            )}
            {!resolving && preview && (
              <span className="text-xs text-green-400">✓ {preview}</span>
            )}
            {!resolving && !preview && userId.trim().length > 0 && /^\d{15,20}$/.test(userId.trim()) && (
              <span className="text-xs text-muted-foreground">Utilisateur inconnu (pas encore sur le serveur ?)</span>
            )}
          </div>
        </div>
        <div className="flex-[2]">
          <label className="text-xs text-muted-foreground mb-1 block">Sujet</label>
          <input
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            placeholder="Décrivez le problème…"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            disabled={loading}
          />
          <div className="mt-1 h-4" />
        </div>
        <button
          type="submit"
          disabled={loading || !userId.trim() || !title.trim()}
          className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50 shrink-0 self-start sm:self-auto mt-1 sm:mt-0"
        >
          {loading ? '…' : 'Créer'}
        </button>
      </form>
      {error && <p className="text-red-400 text-xs mt-2">{error}</p>}
    </div>
  )
}
