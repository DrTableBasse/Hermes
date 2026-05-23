import { headers } from 'next/headers'
import { redirect } from 'next/navigation'
import { auth } from '@/lib/auth'
import { serverListTags } from '@/lib/server-api'
import { ArticleEditor } from '@/components/ArticleEditor'

export default async function NewArticlePage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params

  const session = await auth.api.getSession({ headers: await headers() })
  type UserWithExtras = NonNullable<typeof session>['user'] & { isRedacteur?: boolean }
  const u = session?.user as UserWithExtras | undefined
  if (!u?.isRedacteur) redirect(`/${locale}`)

  const tags = await serverListTags().catch(() => [])

  return (
    <div className="container mx-auto px-4 py-10 max-w-4xl">
      <h1 className="text-3xl font-bold mb-8">Nouvel article</h1>
      <ArticleEditor availableTags={tags} locale={locale} />
    </div>
  )
}
