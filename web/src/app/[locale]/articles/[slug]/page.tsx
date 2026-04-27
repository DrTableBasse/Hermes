import { getTranslations } from 'next-intl/server'
import { notFound } from 'next/navigation'
import { api } from '@/lib/api'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { format } from 'date-fns'
import { fr, enUS } from 'date-fns/locale'

export default async function ArticlePage({
  params,
}: {
  params: Promise<{ locale: string; slug: string }>
}) {
  const { locale, slug } = await params
  const t = await getTranslations('articles')
  const dateLocale = locale === 'fr' ? fr : enUS

  let article: any = null
  try { article = await api.articles.get(slug) } catch {}
  if (!article) notFound()

  return (
    <div className="container mx-auto px-4 py-12 max-w-3xl">
      {article.cover_image_url && (
        <div className="mb-8 rounded-xl overflow-hidden max-h-80">
          <img src={article.cover_image_url} alt={article.title} className="w-full h-full object-cover" />
        </div>
      )}

      {/* Tags */}
      <div className="flex flex-wrap gap-2 mb-4">
        {article.tags.map((tag: any) => (
          <span key={tag.id} className="text-xs px-2 py-0.5 rounded-full font-medium"
                style={{ backgroundColor: tag.color + '33', color: tag.color }}>
            {tag.name}
          </span>
        ))}
      </div>

      <h1 className="text-4xl font-bold mb-4">{article.title}</h1>
      <p className="text-muted-foreground mb-10 text-sm">
        {t('by')} <span className="text-foreground font-medium">{article.author?.username ?? '—'}</span>
        {' · '}
        {format(new Date(article.created_at), 'dd MMMM yyyy', { locale: dateLocale })}
      </p>

      <div className="prose-hermes">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {article.content}
        </ReactMarkdown>
      </div>
    </div>
  )
}
