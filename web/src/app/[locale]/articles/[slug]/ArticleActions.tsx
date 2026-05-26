'use client'

import { useRouter } from 'next/navigation'
import { useState } from 'react'
import Link from 'next/link'
import { actionDeleteArticle } from '@/app/[locale]/articles/actions'

interface Props {
  articleId: number
  articleSlug: string
  locale: string
}

export function ArticleActions({ articleId, articleSlug, locale }: Props) {
  const router  = useRouter()
  const [deleting, setDeleting] = useState(false)
  const [error, setError]       = useState('')

  const handleDelete = async () => {
    if (!confirm('Supprimer cet article définitivement ?')) return
    setDeleting(true)
    setError('')
    try {
      await actionDeleteArticle(articleId)
      router.push(`/${locale}/articles`)
      router.refresh()
    } catch (e: any) {
      setError(e.message)
      setDeleting(false)
    }
  }

  return (
    <div className="flex items-center gap-2">
      <Link
        href={`/${locale}/editor/${articleId}`}
        className="px-3 py-1.5 text-sm border border-border rounded-lg text-muted-foreground hover:text-foreground hover:border-foreground/30 transition-colors"
      >
        Modifier
      </Link>
      <button
        onClick={handleDelete}
        disabled={deleting}
        className="px-3 py-1.5 text-sm border border-destructive/50 rounded-lg text-destructive hover:bg-destructive hover:text-destructive-foreground transition-colors disabled:opacity-50"
      >
        {deleting ? '…' : 'Supprimer'}
      </button>
      {error && <span className="text-xs text-destructive">{error}</span>}
    </div>
  )
}
