import { headers } from 'next/headers'
import { notFound, redirect } from 'next/navigation'
import { auth } from '@/lib/auth'
import { serverListTags, serverGetArticle } from '@/lib/server-api'
import { ArticleEditor } from '@/components/ArticleEditor'

export default async function EditArticlePage({
  params,
}: {
  params: Promise<{ locale: string; id: string }>
}) {
  const { locale, id } = await params

  const session = await auth.api.getSession({ headers: await headers() })
  type UserWithExtras = NonNullable<typeof session>['user'] & {
    isRedacteur?: boolean; isAdmin?: boolean; discordId?: string
  }
  const u = session?.user as UserWithExtras | undefined
  if (!u) redirect(`/${locale}`)

  const token = (session!.session as any).token as string

  // Fetch by slug or numeric id
  let article: any = null
  try {
    // Try slug first, then numeric id
    const isNumeric = /^\d+$/.test(id)
    if (isNumeric) {
      const WEB_API = process.env.WEB_API_INTERNAL_URL ?? 'http://web-api:8000'
      const r = await fetch(`${WEB_API}/articles/by-id/${id}`, {
        headers: { Cookie: `better-auth.session_token=${token}` },
        cache: 'no-store',
      })
      if (r.ok) article = await r.json()
    } else {
      article = await serverGetArticle(id, token)
    }
  } catch {}

  if (!article) notFound()

  const isAuthor = u.discordId === String(article.author_id)
  if (!isAuthor && !u.isAdmin && !u.isRedacteur) redirect(`/${locale}`)

  const tags = await serverListTags().catch(() => [])

  return (
    <div className="container mx-auto px-4 py-10 max-w-4xl">
      <h1 className="text-3xl font-bold mb-8">Modifier l'article</h1>
      <ArticleEditor article={article} availableTags={tags} locale={locale} />
    </div>
  )
}
