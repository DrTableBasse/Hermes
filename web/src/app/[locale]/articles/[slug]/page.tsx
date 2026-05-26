import { headers } from 'next/headers'
import { notFound } from 'next/navigation'
import { auth } from '@/lib/auth'
import { serverGetArticle } from '@/lib/server-api'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { format } from 'date-fns'
import { fr, enUS } from 'date-fns/locale'
import { ArticleActions } from './ArticleActions'

type UserWithExtras = {
  isAdmin?: boolean; isRedacteur?: boolean; discordId?: string
} & Record<string, unknown>

export default async function ArticlePage({
  params,
}: {
  params: Promise<{ locale: string; slug: string }>
}) {
  const { locale, slug } = await params
  const dateLocale = locale === 'fr' ? fr : enUS

  const session = await auth.api.getSession({ headers: await headers() }).catch(() => null)
  const u = session?.user as UserWithExtras | undefined
  const token = session ? (session.session as any).token as string : undefined

  let article: any = null
  try { article = await serverGetArticle(slug, token) } catch {}
  if (!article) notFound()

  const isAuthor  = u?.discordId === String(article.author_id)
  const canEdit   = isAuthor || !!u?.isAdmin || !!u?.isRedacteur

  return (
    <div className="container mx-auto px-4 py-12 max-w-3xl">
      {article.cover_image_url && (
        <div className="mb-8 rounded-xl overflow-hidden max-h-80">
          <img src={article.cover_image_url} alt={article.title} className="w-full h-full object-cover" />
        </div>
      )}

      {/* Tags */}
      {article.tags.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-4">
          {article.tags.map((tag: any) => (
            <span key={tag.id} className="text-xs px-2 py-0.5 rounded-full font-medium"
                  style={{ backgroundColor: tag.color + '33', color: tag.color }}>
              {tag.name}
            </span>
          ))}
        </div>
      )}

      {/* Title + actions */}
      <div className="flex flex-wrap items-start justify-between gap-4 mb-4">
        <h1 className="text-4xl font-bold flex-1">{article.title}</h1>
        {canEdit && (
          <ArticleActions articleId={article.id} articleSlug={slug} locale={locale} />
        )}
      </div>

      {!article.published && (
        <div className="mb-4 px-3 py-1.5 bg-yellow-500/10 border border-yellow-500/30 rounded-lg text-yellow-600 dark:text-yellow-400 text-sm inline-block">
          Brouillon — non publié
        </div>
      )}

      <p className="text-muted-foreground mb-10 text-sm">
        Par <span className="text-foreground font-medium">{article.author?.username ?? '—'}</span>
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
