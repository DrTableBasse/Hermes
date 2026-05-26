'use client'
import { useState, useEffect } from 'react'
import { api, Comment, User } from '@/lib/api'

interface Props {
  articleId: number
  currentUser: User | null
}

export default function ArticleComments({ articleId, currentUser }: Props) {
  const [comments, setComments] = useState<Comment[]>([])
  const [content, setContent] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    api.comments.list(articleId).then(r => setComments(r.comments)).catch(() => {})
  }, [articleId])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!content.trim() || loading) return
    setLoading(true)
    try {
      const comment = await api.comments.create({ article_id: articleId, content: content.trim() })
      setComments(prev => [...prev, comment])
      setContent('')
    } catch {}
    setLoading(false)
  }

  const handleDelete = async (id: number) => {
    try {
      await api.comments.delete(id)
      setComments(prev => prev.filter(c => c.id !== id))
    } catch {}
  }

  const handleVote = async (id: number) => {
    try {
      await api.comments.vote(id)
      setComments(prev => prev.map(c =>
        c.id === id ? { ...c, vote_count: c.vote_count + 1 } : c
      ))
    } catch {}
  }

  return (
    <section className="mt-12 border-t border-white/10 pt-8">
      <h3 className="text-lg font-semibold mb-6">Commentaires ({comments.length})</h3>

      {currentUser && (
        <form onSubmit={handleSubmit} className="mb-8">
          <textarea
            value={content}
            onChange={e => setContent(e.target.value)}
            placeholder="Écrire un commentaire..."
            rows={3}
            maxLength={2000}
            className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl resize-none text-sm focus:outline-none focus:border-blue-500/50 transition-colors"
          />
          <div className="flex justify-end mt-2">
            <button
              type="submit"
              disabled={loading || !content.trim()}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-sm rounded-lg transition-colors"
            >
              {loading ? 'Envoi...' : 'Commenter'}
            </button>
          </div>
        </form>
      )}

      <div className="space-y-4">
        {comments.map(c => (
          <div key={c.id} className="flex gap-3">
            {c.discord_avatar ? (
              <img src={c.discord_avatar} alt={c.username} className="w-8 h-8 rounded-full flex-shrink-0" />
            ) : (
              <div className="w-8 h-8 rounded-full bg-gray-700 flex-shrink-0" />
            )}
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-sm font-medium">{c.username}</span>
                <span className="text-xs text-gray-500">{new Date(c.created_at).toLocaleDateString('fr-FR')}</span>
              </div>
              <p className="text-sm text-gray-300 whitespace-pre-wrap">{c.content}</p>
              <div className="flex items-center gap-3 mt-2">
                <button
                  onClick={() => handleVote(c.id)}
                  className="flex items-center gap-1 text-xs text-gray-400 hover:text-blue-400 transition-colors"
                >
                  👍 {c.vote_count}
                </button>
                {currentUser && String(currentUser.user_id) === String(c.user_id) && (
                  <button
                    onClick={() => handleDelete(c.id)}
                    className="text-xs text-gray-400 hover:text-red-400 transition-colors"
                  >
                    Supprimer
                  </button>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}
