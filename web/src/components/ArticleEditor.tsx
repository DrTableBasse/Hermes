'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import dynamic from 'next/dynamic'
import type { Tag, Article } from '@/lib/api'
import {
  actionCreateArticle,
  actionUpdateArticle,
  actionUploadMedia,
} from '@/app/[locale]/articles/actions'

const MDEditor = dynamic(() => import('@uiw/react-md-editor'), { ssr: false })

interface Props {
  article?: Article
  availableTags: Tag[]
  locale: string
}

export function ArticleEditor({ article, availableTags, locale }: Props) {
  const router  = useRouter()
  const isEdit  = !!article

  const [title,    setTitle]    = useState(article?.title ?? '')
  const [content,  setContent]  = useState(article?.content ?? '')
  const [coverUrl, setCoverUrl] = useState(article?.cover_image_url ?? '')
  const [selTags,  setSelTags]  = useState<number[]>(article?.tags.map(t => t.id) ?? [])
  const [saving,   setSaving]   = useState(false)
  const [error,    setError]    = useState('')

  const toggleTag = (id: number) =>
    setSelTags(prev => prev.includes(id) ? prev.filter(t => t !== id) : [...prev, id])

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    try {
      const formData = new FormData()
      formData.append('file', file)
      const res = await actionUploadMedia(formData)
      const url = `${process.env.NEXT_PUBLIC_API_URL}${res.url}`
      setContent(prev => `${prev}\n![${file.name}](${url})`)
    } catch (e: any) {
      setError(e.message)
    }
  }

  const handleSubmit = async (publish: boolean) => {
    if (!title.trim() || !content.trim()) {
      setError('Titre et contenu requis')
      return
    }
    setSaving(true)
    setError('')
    try {
      const payload = {
        title: title.trim(),
        content,
        cover_image_url: coverUrl.trim() || undefined,
        published: publish,
        tag_ids: selTags,
      }
      const result = isEdit
        ? await actionUpdateArticle(article!.id, payload)
        : await actionCreateArticle(payload)
      router.push(`/${locale}/articles/${result.slug}`)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-5" data-color-mode="dark">
      <input
        value={title}
        onChange={e => setTitle(e.target.value)}
        placeholder="Titre de l'article"
        className="w-full bg-card border border-border rounded-lg px-4 py-3 text-xl font-semibold focus:outline-none focus:ring-2 focus:ring-primary"
      />

      <input
        value={coverUrl}
        onChange={e => setCoverUrl(e.target.value)}
        placeholder="URL de l'image de couverture (optionnel)"
        className="w-full bg-card border border-border rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
      />
      {coverUrl && (
        <div className="rounded-lg overflow-hidden max-h-48">
          <img src={coverUrl} alt="Aperçu couverture" className="w-full h-full object-cover" />
        </div>
      )}

      <div>
        <p className="text-sm font-medium mb-2">Tags</p>
        {availableTags.length === 0 ? (
          <p className="text-sm text-muted-foreground">Aucun tag disponible. Créez-en depuis la page Articles.</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {availableTags.map(tag => (
              <button
                key={tag.id}
                type="button"
                onClick={() => toggleTag(tag.id)}
                className="px-3 py-1 rounded-full text-sm font-medium border transition-all"
                style={selTags.includes(tag.id)
                  ? { borderColor: tag.color, color: tag.color, backgroundColor: tag.color + '33' }
                  : { borderColor: 'var(--border)', color: 'var(--muted-foreground)' }}
              >
                {tag.name}
              </button>
            ))}
          </div>
        )}
      </div>

      <label className="cursor-pointer inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground border border-border rounded-lg px-3 py-2 transition-colors">
        Insérer une image
        <input type="file" accept="image/*" className="hidden" onChange={handleUpload} />
      </label>

      <div className="rounded-lg overflow-hidden border border-border">
        <MDEditor value={content} onChange={v => setContent(v ?? '')} height={520} />
      </div>

      {error && <p className="text-destructive text-sm">{error}</p>}

      <div className="flex gap-3 pt-2">
        <button
          onClick={() => handleSubmit(true)}
          disabled={saving}
          className="bg-primary text-primary-foreground px-6 py-2 rounded-lg font-medium hover:opacity-90 disabled:opacity-50"
        >
          {saving ? '…' : isEdit ? 'Mettre à jour et publier' : 'Publier'}
        </button>
        <button
          onClick={() => handleSubmit(false)}
          disabled={saving}
          className="bg-secondary text-secondary-foreground px-6 py-2 rounded-lg font-medium hover:opacity-90 disabled:opacity-50"
        >
          {saving ? '…' : isEdit ? 'Sauvegarder brouillon' : 'Brouillon'}
        </button>
        <button
          onClick={() => router.back()}
          className="px-4 py-2 text-sm text-muted-foreground hover:text-foreground"
        >
          Annuler
        </button>
      </div>
    </div>
  )
}
