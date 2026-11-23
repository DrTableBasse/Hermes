import type { Metadata } from "next"
import { notFound, redirect } from "next/navigation"
import { ArticleEditor } from "@/components/articles/article-editor"
import { SectionHeading } from "@/components/ui/section-heading"
import { getArticle, getArticleById, getSessionUser, listTags } from "@/lib/api/server"
import type { Article } from "@/lib/api/types"
import { canEdit } from "@/lib/articles"
import { isUnknownMember } from "@/lib/members"
import { sessionToken } from "@/lib/session"

export const metadata: Metadata = { title: "Modifier l’article · SaucisseLand" }

/** Article à éditer, par identifiant numérique ou par slug ; `null` : introuvable, `Error` : web-api injoignable. */
async function load(id: string, token: string): Promise<Article | null | Error> {
  try {
    return /^\d+$/.test(id) ? await getArticleById(Number(id), token) : await getArticle(id, token)
  } catch (error) {
    return isUnknownMember(error) ? null : error instanceof Error ? error : new Error(String(error))
  }
}

/** Modification : l'auteur ou un administrateur (même règle que `PUT /articles/{id}`). */
export default async function EditArticlePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  const token = await sessionToken()
  if (!token) redirect("/")

  const [me, article] = await Promise.all([getSessionUser(token), load(id, token)])
  if (!me) redirect("/")
  if (article === null) notFound()
  if (article instanceof Error) {
    return (
      <main className="relative pt-10 pb-24">
        <div className="relative mx-auto max-w-[900px] px-6">
          <p className="rounded-2xl border border-line bg-[rgb(19_22_42/0.6)] px-6 py-5 text-muted" role="status">
            Cet article est injoignable pour l’instant. Reviens dans un moment.
          </p>
        </div>
      </main>
    )
  }
  if (!canEdit(me, article)) redirect("/")

  const tags = await listTags().catch(() => [])

  return (
    <main className="relative pt-10 pb-24">
      <div className="relative mx-auto max-w-[900px] px-6">
        <SectionHeading as="h1" title="Modifier l’article" className="mb-8" />
        <ArticleEditor article={article} availableTags={tags} />
      </div>
    </main>
  )
}
