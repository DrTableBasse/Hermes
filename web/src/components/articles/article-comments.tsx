"use client"

import { useEffect, useState } from "react"
import { Avatar } from "@/components/ui/avatar"
import { api } from "@/lib/api/client"
import type { ArticleComment, Snowflake } from "@/lib/api/types"
import { formatDate } from "@/lib/format"

type Props = {
  articleId: number
  /** Membre connecté (`/auth/me`) ; `null` : lecture seule. */
  viewer: { user_id: Snowflake; is_admin: boolean } | null
}

const message = (e: unknown) => (e instanceof Error ? e.message : "Erreur inattendue")

/** Commentaires d'un article : lecture publique, écriture, vote et suppression pour les membres connectés. */
export function ArticleComments({ articleId, viewer }: Props) {
  const [comments, setComments] = useState<ArticleComment[]>([])
  const [loaded, setLoaded] = useState(false)
  const [failed, setFailed] = useState(false)
  const [content, setContent] = useState("")
  const [sending, setSending] = useState(false)
  const [error, setError] = useState("")

  useEffect(() => {
    let alive = true
    api.comments
      .list(articleId)
      .then(r => alive && setComments(r.comments))
      .catch(() => alive && setFailed(true))
      .finally(() => alive && setLoaded(true))
    return () => {
      alive = false
    }
  }, [articleId])

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!content.trim() || sending) return
    setSending(true)
    setError("")
    try {
      const comment = await api.comments.create({ article_id: articleId, content: content.trim() })
      setComments(prev => [...prev, comment])
      setContent("")
    } catch (err) {
      setError(message(err))
    } finally {
      setSending(false)
    }
  }

  async function remove(id: number) {
    setError("")
    try {
      await api.comments.delete(id)
      setComments(prev => prev.filter(c => c.id !== id))
    } catch (err) {
      setError(message(err))
    }
  }

  async function vote(id: number) {
    setError("")
    try {
      // web-api bascule le vote : `voted` dit dans quel sens le compteur a bougé.
      const { voted } = await api.comments.vote(id)
      setComments(prev => prev.map(c => (c.id === id ? { ...c, vote_count: c.vote_count + (voted ? 1 : -1) } : c)))
    } catch (err) {
      setError(message(err))
    }
  }

  return (
    <section aria-labelledby="comments-title" className="mt-12 border-t border-line pt-8">
      <h2 id="comments-title" className="mb-6 font-display text-xl font-bold">
        {loaded && !failed ? `Commentaires (${comments.length})` : "Commentaires"}
      </h2>

      {viewer && (
        <form onSubmit={submit} className="mb-8">
          <textarea
            value={content}
            onChange={e => setContent(e.target.value)}
            placeholder="Écrire un commentaire…"
            aria-label="Écrire un commentaire"
            rows={3}
            maxLength={2000}
            className="w-full resize-none rounded-xl border border-line bg-white/5 px-4 py-3 text-sm text-fg placeholder:text-muted focus:border-violet/60 focus:outline-none"
          />
          <div className="mt-2 flex justify-end">
            <button
              type="submit"
              disabled={sending || !content.trim()}
              className="rounded-lg bg-violet-deep px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
            >
              {sending ? "Envoi…" : "Commenter"}
            </button>
          </div>
        </form>
      )}
      {error && (
        <p role="alert" className="mb-4 text-sm text-[#FF8F8F]">
          {error}
        </p>
      )}

      {failed && (
        <p role="status" className="text-sm text-muted">
          Commentaires indisponibles pour l’instant.
        </p>
      )}
      {loaded && !failed && comments.length === 0 && <p className="text-sm text-muted">Aucun commentaire pour l’instant.</p>}
      <ul className="space-y-5">
        {comments.map(c => (
          <li key={c.id} className="flex gap-3">
            <Avatar name={c.username} src={c.discord_avatar} size={32} />
            <div className="min-w-0 flex-1">
              <div className="mb-1 flex items-center gap-2">
                <span className="text-sm font-medium">{c.username}</span>
                <span className="text-xs text-muted">{formatDate(c.created_at)}</span>
              </div>
              <p className="text-sm whitespace-pre-wrap text-msg [overflow-wrap:anywhere]">{c.content}</p>
              <div className="mt-2 flex items-center gap-3">
                {viewer ? (
                  <button
                    type="button"
                    onClick={() => vote(c.id)}
                    aria-label={`Voter pour le commentaire de ${c.username}`}
                    className="text-xs text-muted hover:text-cyan"
                  >
                    👍 {c.vote_count}
                  </button>
                ) : (
                  <span className="text-xs text-muted">👍 {c.vote_count}</span>
                )}
                {viewer && (String(viewer.user_id) === String(c.user_id) || viewer.is_admin) && (
                  <button type="button" onClick={() => remove(c.id)} className="text-xs text-muted hover:text-[#FF8F8F]">
                    Supprimer
                  </button>
                )}
              </div>
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}
