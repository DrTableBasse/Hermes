import type { Metadata } from 'next'
import { headers } from 'next/headers'
import { Suspense } from 'react'
import Link from 'next/link'
import { auth } from '@/lib/auth'
import { serverListArticles, serverListTags, serverMyArticles } from '@/lib/server-api'
import { ArticleCard } from '@/components/ArticleCard'
import { SearchBar } from './SearchBar'
import { TagManager } from './TagManager'

type UserWithExtras = {
  isAdmin?: boolean; isRedacteur?: boolean
} & Record<string, unknown>

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>
}): Promise<Metadata> {
  const { locale } = await params
  const isFr = locale === 'fr'
  return {
    title: isFr ? 'Articles' : 'Articles',
    description: isFr
      ? 'Découvrez les articles et actualités de la communauté SaucisseLand.'
      : 'Discover articles and news from the SaucisseLand community.',
  }
}

export default async function ArticlesPage({
  params,
  searchParams,
}: {
  params: Promise<{ locale: string }>
  searchParams: Promise<{ page?: string; tag?: string; q?: string }>
}) {
  const { locale }          = await params
  const { page: ps, tag, q } = await searchParams
  const page   = Math.max(1, parseInt(ps ?? '1', 10))
  const search = q?.trim() || undefined

  const session = await auth.api.getSession({ headers: await headers() }).catch(() => null)
  const u = session?.user as UserWithExtras | undefined
  const isRedacteur = !!u?.isRedacteur
  const token = session ? (session.session as any).token as string : undefined

  const [listResult, tags, myDrafts] = await Promise.all([
    serverListArticles({ page, limit: 12, tag, search }).catch(() => ({ articles: [], total: 0, page: 1, limit: 12 })),
    serverListTags().catch(() => []),
    isRedacteur && token ? serverMyArticles(token).catch(() => []) : Promise.resolve([]),
  ])

  const { articles, total } = listResult
  const totalPages = Math.ceil(total / 12)
  const drafts     = (myDrafts as any[]).filter(a => !a.published)

  return (
    <div className="container mx-auto px-4 py-12">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 mb-8">
        <h1 className="text-3xl font-extrabold tracking-tight">Articles</h1>
        <div className="flex items-center gap-3">
          <Suspense><SearchBar defaultValue={q ?? ''} /></Suspense>
          {isRedacteur && (
            <Link
              href={`/${locale}/editor/new`}
              className="px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:opacity-90"
            >
              + Nouvel article
            </Link>
          )}
        </div>
      </div>

      {/* Tag filter */}
      {tags.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-6">
          <Link
            href={`/${locale}/articles${search ? `?q=${search}` : ''}`}
            className={`px-3 py-1 rounded-full text-sm font-medium border transition-colors ${
              !tag ? 'border-primary text-primary' : 'border-border text-muted-foreground hover:text-foreground'
            }`}
          >
            Tous
          </Link>
          {tags.map(tg => {
            const active = tag === tg.slug
            const href   = `/${locale}/articles?tag=${tg.slug}${search ? `&q=${search}` : ''}`
            return (
              <Link
                key={tg.id}
                href={href}
                className="px-3 py-1 rounded-full text-sm font-medium border transition-colors"
                style={active
                  ? { borderColor: tg.color, color: tg.color, backgroundColor: tg.color + '22' }
                  : {}}
              >
                {tg.name}
              </Link>
            )
          })}
        </div>
      )}

      {/* Tag manager (rédacteurs only) */}
      {isRedacteur && (
        <div className="mb-8">
          <TagManager initialTags={tags} />
        </div>
      )}

      {/* My drafts section */}
      {drafts.length > 0 && (
        <section className="mb-10">
          <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <span className="text-muted-foreground">✏️</span> Mes brouillons
            <span className="text-xs font-normal text-muted-foreground bg-secondary px-2 py-0.5 rounded-full">
              {drafts.length}
            </span>
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {drafts.map((a: any) => (
              <ArticleCard key={a.id} article={a} locale={locale} isDraft />
            ))}
          </div>
        </section>
      )}

      {/* Search results info */}
      {(search || tag) && (
        <p className="text-sm text-muted-foreground mb-4">
          {total} article{total > 1 ? 's' : ''}
          {search && <span> pour « <strong className="text-foreground">{search}</strong> »</span>}
          {tag    && <span> dans le tag <strong className="text-foreground">{tag}</strong></span>}
        </p>
      )}

      {/* Articles grid */}
      {articles.length === 0 ? (
        <p className="text-muted-foreground text-center py-20">
          {search ? `Aucun résultat pour « ${search} »` : 'Aucun article publié pour le moment.'}
        </p>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6 mb-10">
          {articles.map(a => <ArticleCard key={a.id} article={a} locale={locale} />)}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex justify-center gap-2">
          {Array.from({ length: totalPages }, (_, i) => i + 1).map(p => {
            const href = `/${locale}/articles?page=${p}${tag ? `&tag=${tag}` : ''}${search ? `&q=${search}` : ''}`
            return (
              <Link
                key={p}
                href={href}
                className={`w-9 h-9 flex items-center justify-center rounded border text-sm ${
                  p === page ? 'border-primary text-primary' : 'border-border text-muted-foreground hover:text-foreground'
                }`}
              >
                {p}
              </Link>
            )
          })}
        </div>
      )}
    </div>
  )
}
