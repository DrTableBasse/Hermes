import Link from 'next/link'
import { format } from 'date-fns'
import { fr, enUS } from 'date-fns/locale'
import type { Article } from '@/lib/api'

interface Props { article: Article; locale: string; isDraft?: boolean }

export function ArticleCard({ article, locale, isDraft }: Props) {
  const dateLocale = locale === 'fr' ? fr : enUS
  return (
    <div className="glass-card-hover flex flex-col overflow-hidden group">
      {article.cover_image_url && (
        <div className="h-48 overflow-hidden">
          <img src={article.cover_image_url} alt={article.title}
               className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500" />
        </div>
      )}
      <div className="p-5 flex flex-col flex-1">
        <div className="flex flex-wrap gap-1.5 mb-3">
          {isDraft && (
            <span className="text-xs px-2.5 py-0.5 rounded-full font-medium bg-warning/10 text-warning border border-warning/30">
              Brouillon
            </span>
          )}
          {article.tags.map(tag => (
            <span key={tag.id} className="text-xs px-2.5 py-0.5 rounded-full font-medium"
                  style={{ backgroundColor: tag.color + '1a', color: tag.color, borderColor: tag.color + '33', borderWidth: 1 }}>
              {tag.name}
            </span>
          ))}
        </div>
        <h3 className="font-semibold text-lg mb-2 line-clamp-2 group-hover:text-primary transition-colors">
          {article.title}
        </h3>
        <p className="text-sm text-muted-foreground mb-4">
          Par <span className="text-foreground font-medium">{article.author?.username ?? '—'}</span>
          {' · '}
          {format(new Date(article.created_at), 'dd MMM yyyy', { locale: dateLocale })}
        </p>
        <div className="mt-auto flex items-center justify-between">
          <Link href={`/${locale}/articles/${article.slug}`}
                className="text-sm font-medium text-primary hover:underline">
            Lire la suite →
          </Link>
          {isDraft && (
            <Link href={`/${locale}/editor/${article.id}`}
                  className="text-xs text-muted-foreground hover:text-foreground border border-border rounded-md px-2.5 py-1 transition-colors">
              Modifier
            </Link>
          )}
        </div>
      </div>
    </div>
  )
}
