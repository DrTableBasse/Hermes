import { getTranslations } from 'next-intl/server'
import Link from 'next/link'
import { api } from '@/lib/api'
import { ArticleCard } from '@/components/ArticleCard'

export default async function ArticlesPage({
  params, searchParams,
}: {
  params: Promise<{ locale: string }>
  searchParams: Promise<{ page?: string; tag?: string }>
}) {
  const { locale } = await params
  const { page: pageStr, tag } = await searchParams
  const page = parseInt(pageStr ?? '1', 10)
  const t  = await getTranslations('articles')
  const tc = await getTranslations('common')

  let articles: any[] = []
  let total = 0
  let tags: any[] = []
  try {
    const res = await api.articles.list(page, 12, tag)
    articles  = res.articles
    total     = res.total
    tags      = (await api.tags.list()).tags
  } catch {}

  const totalPages = Math.ceil(total / 12)

  return (
    <div className="container mx-auto px-4 py-12">
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-3xl font-bold">{t('title')}</h1>
        {/* New article button — shown only for logged-in redacteurs (client component needed for auth check) */}
      </div>

      {/* Tag filter */}
      {tags.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-8">
          <Link href={`/${locale}/articles`}
                className={`px-3 py-1 rounded-full text-sm font-medium border transition-colors ${!tag ? 'border-primary text-primary' : 'border-border text-muted-foreground hover:text-foreground'}`}>
            Tous
          </Link>
          {tags.map(tg => (
            <Link key={tg.id}
                  href={`/${locale}/articles?tag=${tg.slug}`}
                  className="px-3 py-1 rounded-full text-sm font-medium border transition-colors"
                  style={tag === tg.slug
                    ? { borderColor: tg.color, color: tg.color, backgroundColor: tg.color + '22' }
                    : {}}>
              {tg.name}
            </Link>
          ))}
        </div>
      )}

      {articles.length === 0 ? (
        <p className="text-muted-foreground text-center py-20">{t('no_articles')}</p>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6 mb-10">
          {articles.map(a => <ArticleCard key={a.id} article={a} locale={locale} t={t} />)}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex justify-center gap-2">
          {Array.from({ length: totalPages }, (_, i) => i + 1).map(p => (
            <Link key={p}
                  href={`/${locale}/articles?page=${p}${tag ? `&tag=${tag}` : ''}`}
                  className={`w-9 h-9 flex items-center justify-center rounded border text-sm ${p === page ? 'border-primary text-primary' : 'border-border text-muted-foreground hover:text-foreground'}`}>
              {p}
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
