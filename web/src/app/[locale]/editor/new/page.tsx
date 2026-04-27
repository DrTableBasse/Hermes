'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useTranslations } from 'next-intl'
import dynamic from 'next/dynamic'
import { api, type Tag } from '@/lib/api'

const MDEditor = dynamic(() => import('@uiw/react-md-editor'), { ssr: false })

export default function NewArticlePage({ params }: { params: Promise<{ locale: string }> }) {
  const t      = useTranslations('editor')
  const router = useRouter()
  const [locale, setLocale] = useState('fr')
  const [title,    setTitle]    = useState('')
  const [content,  setContent]  = useState('')
  const [coverUrl, setCoverUrl] = useState('')
  const [published, setPublished] = useState(false)
  const [tags,     setTags]     = useState<Tag[]>([])
  const [selTags,  setSelTags]  = useState<number[]>([])
  const [saving,   setSaving]   = useState(false)
  const [error,    setError]    = useState('')

  useEffect(() => {
    params.then(p => setLocale(p.locale))
    api.tags.list().then(r => setTags(r.tags)).catch(() => {})
  }, [])

  const toggleTag = (id: number) =>
    setSelTags(prev => prev.includes(id) ? prev.filter(t => t !== id) : [...prev, id])

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    const res  = await api.media.upload(file)
    setContent(prev => `${prev}\n![${file.name}](${process.env.NEXT_PUBLIC_API_URL}${res.url})`)
  }

  const handleSubmit = async (pub: boolean) => {
    if (!title.trim() || !content.trim()) { setError('Titre et contenu requis'); return }
    setSaving(true); setError('')
    try {
      const art = await api.articles.create({
        title, content, cover_image_url: coverUrl || undefined,
        published: pub, tag_ids: selTags,
      })
      router.push(`/${locale}/articles/${art.slug}`)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="container mx-auto px-4 py-10 max-w-4xl" data-color-mode="dark">
      <h1 className="text-3xl font-bold mb-8">✏️ {t('title_placeholder')}</h1>

      <div className="space-y-4 mb-6">
        <input
          value={title}
          onChange={e => setTitle(e.target.value)}
          placeholder={t('title_placeholder')}
          className="w-full bg-card border border-border rounded-lg px-4 py-3 text-xl font-semibold focus:outline-none focus:ring-2 focus:ring-primary"
        />
        <input
          value={coverUrl}
          onChange={e => setCoverUrl(e.target.value)}
          placeholder={t('cover_url')}
          className="w-full bg-card border border-border rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
        />
      </div>

      {/* Tags */}
      <div className="mb-4">
        <p className="text-sm font-medium mb-2">{t('tags')}</p>
        <div className="flex flex-wrap gap-2">
          {tags.map(tag => (
            <button key={tag.id} type="button" onClick={() => toggleTag(tag.id)}
                    className="px-3 py-1 rounded-full text-sm font-medium border transition-colors"
                    style={selTags.includes(tag.id)
                      ? { borderColor: tag.color, color: tag.color, backgroundColor: tag.color + '33' }
                      : { borderColor: 'var(--border)', color: 'var(--muted-foreground)' }}>
              {tag.name}
            </button>
          ))}
        </div>
      </div>

      {/* Image upload */}
      <div className="mb-4">
        <label className="cursor-pointer inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground border border-border rounded-lg px-3 py-2 transition-colors">
          🖼️ {t('upload_image')}
          <input type="file" accept="image/*" className="hidden" onChange={handleUpload} />
        </label>
      </div>

      {/* Editor */}
      <div className="mb-6 rounded-lg overflow-hidden border border-border">
        <MDEditor value={content} onChange={v => setContent(v ?? '')} height={500} />
      </div>

      {error && <p className="text-destructive text-sm mb-4">{error}</p>}

      <div className="flex gap-3">
        <button onClick={() => handleSubmit(true)} disabled={saving}
                className="bg-primary text-primary-foreground px-6 py-2 rounded-lg font-medium hover:opacity-90 disabled:opacity-50">
          {saving ? '…' : t('publish')}
        </button>
        <button onClick={() => handleSubmit(false)} disabled={saving}
                className="bg-secondary text-secondary-foreground px-6 py-2 rounded-lg font-medium hover:opacity-90 disabled:opacity-50">
          {saving ? '…' : t('save_draft')}
        </button>
      </div>
    </div>
  )
}
