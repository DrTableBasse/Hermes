import Link from 'next/link'
import { format } from 'date-fns'
import { fr, enUS } from 'date-fns/locale'
import type { Article } from '@/lib/api'

interface Props { article: Article; locale: string; t: (k: string) => string }

export function ArticleCard({ article, locale, t }: Props) {
  const dateLocale = locale === 'fr' ? fr : enUS
  return (
    <div className="flex flex-col border border-border rounded-xl overflow-hidden hover:border-primary/50 transition-colors bg-card">
      {article.cover_image_url && (
        <div className="h-48 overflow-hidden">
          <img src={article.cover_image_url} alt={article.title}
               className="w-full h-full object-cover" />
        </div>
      )}
      <div className="p-5 flex flex-col flex-1">
        <div className="flex flex-wrap gap-1.5 mb-3">
          {article.tags.map(tag => (
            <span key={tag.id} className="text-xs px-2 py-0.5 rounded-full font-medium"
                  style={{ backgroundColor: tag.color + '33', color: tag.color }}>
              {tag.name}
            </span>
          ))}
        </div>
        <h3 className="font-semibold text-lg mb-2 line-clamp-2">{article.title}</h3>
        <p className="text-sm text-muted-foreground mb-4">
          {t('by')} <span className="text-foreground">{article.author?.username ?? '—'}</span>
          {' · '}
          {format(new Date(article.created_at), 'dd MMM yyyy', { locale: dateLocale })}
        </p>
        <div className="mt-auto">
          <Link href={`/${locale}/articles/${article.slug}`}
                className="text-sm font-medium text-primary hover:underline">
            {t('read_more')} →
          </Link>
        </div>
      </div>
    </div>
  )
}
