import type { Metadata } from "next"
import { redirect } from "next/navigation"
import { ArticleEditor } from "@/components/articles/article-editor"
import { SectionHeading } from "@/components/ui/section-heading"
import { getSessionUser, listTags } from "@/lib/api/server"
import { canWrite } from "@/lib/articles"
import { sessionToken } from "@/lib/session"

export const metadata: Metadata = { title: "Nouvel article · SaucisseLand" }

/** Création d'un article : rédacteurs et administrateurs (le middleware ne contrôle que la présence de la session). */
export default async function NewArticlePage() {
  const token = await sessionToken()
  const me = token ? await getSessionUser(token) : null
  if (!canWrite(me)) redirect("/")

  const tags = await listTags().catch(() => [])

  return (
    <main className="relative pt-10 pb-24">
      <div className="relative mx-auto max-w-[900px] px-6">
        <SectionHeading as="h1" title="Nouvel article" className="mb-8" />
        <ArticleEditor availableTags={tags} />
      </div>
    </main>
  )
}
