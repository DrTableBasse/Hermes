import type { Metadata } from "next"
import { OG_IMAGES } from "@/lib/site"
import Image from "next/image"
import Link from "next/link"
import { notFound } from "next/navigation"
import { ArticleActions } from "@/components/articles/article-actions"
import { ArticleComments } from "@/components/articles/article-comments"
import { TagChips } from "@/components/articles/article-card"
import { Markdown } from "@/components/articles/markdown"
import { Avatar } from "@/components/ui/avatar"
import { Chip } from "@/components/ui/chip"
import { getArticle, getSessionUser } from "@/lib/api/server"
import type { Article } from "@/lib/api/types"
import { canEdit, excerpt, safeImageSrc } from "@/lib/articles"
import { formatDate } from "@/lib/format"
import { isUnknownMember } from "@/lib/members"
import { sessionToken } from "@/lib/session"

type Props = { params: Promise<{ slug: string }> }

/** Article ; `null` : introuvable (ou brouillon d'un autre), `Error` : web-api injoignable. */
async function load(slug: string, token: string | null): Promise<Article | null | Error> {
  try {
    return await getArticle(slug, token ?? undefined)
  } catch (error) {
    return isUnknownMember(error) ? null : error instanceof Error ? error : new Error(String(error))
  }
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params
  const article = await load(slug, null)
  if (!article || article instanceof Error) return { title: "Article · SaucisseLand" }
  const description = excerpt(article.content)
  const cover = safeImageSrc(article.cover_image_url)
  return {
    title: `${article.title} · SaucisseLand`,
    description,
    openGraph: {
      title: article.title,
      description,
      type: "article",
      locale: "fr_FR",
      images: cover ? [{ url: cover }] : OG_IMAGES,
    },
  }
}

export default async function ArticlePage({ params }: Props) {
  const { slug } = await params
  const token = await sessionToken()
  const [article, me] = await Promise.all([load(slug, token), token ? getSessionUser(token) : null])

  if (article === null) notFound()
  if (article instanceof Error) {
    return (
      <main className="relative pt-10 pb-24">
        <div className="relative mx-auto max-w-[760px] px-6">
          <p className="rounded-2xl border border-line bg-[rgb(19_22_42/0.6)] px-6 py-5 text-muted" role="status">
            Cet article est injoignable pour l’instant. Hermes recompte, reviens dans un moment.
          </p>
        </div>
      </main>
    )
  }

  const cover = safeImageSrc(article.cover_image_url)
  const editable = canEdit(me, article)

  return (
    <main className="relative pt-10 pb-24">
      <article className="relative mx-auto max-w-[760px] px-6">
        <Link href="/articles" prefetch={false} className="text-sm text-muted hover:text-fg">
          ← Tous les articles
        </Link>

        {cover && (
          <div className="relative mt-6 mb-8 h-80 overflow-hidden rounded-[20px]">
            <Image src={cover} alt="" fill unoptimized priority sizes="(max-width: 768px) 100vw, 760px" className="object-cover" />
          </div>
        )}

        {article.tags.length > 0 && (
          <div className="mt-6 mb-4 flex flex-wrap gap-2">
            <TagChips tags={article.tags} />
          </div>
        )}

        <div className="flex flex-wrap items-start justify-between gap-4">
          <h1 className="min-w-0 flex-1 font-display text-[clamp(32px,4.2vw,48px)] leading-[1.05] font-extrabold tracking-[-0.03em] text-balance">
            {article.title}
          </h1>
          {editable && <ArticleActions articleId={article.id} />}
        </div>

        {!article.published && (
          <div className="mt-4">
            <Chip color="var(--color-gold)">Brouillon — non publié</Chip>
          </div>
        )}

        <p className="mt-4 mb-10 flex items-center gap-2 text-sm text-muted">
          {article.author && <Avatar name={article.author.username} src={article.author.discord_avatar} size={26} />}
          <span>
            Par <span className="font-medium text-fg">{article.author?.username ?? "—"}</span> · {formatDate(article.created_at)}
          </span>
        </p>

        <Markdown>{article.content}</Markdown>

        {article.published && <ArticleComments articleId={article.id} viewer={me} />}
      </article>
    </main>
  )
}
