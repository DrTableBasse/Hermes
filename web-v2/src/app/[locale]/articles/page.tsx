import type { Metadata } from "next"
import Link from "next/link"
import { Suspense } from "react"
import { ArticleCard } from "@/components/articles/article-card"
import { TagManager } from "@/components/articles/tag-manager"
import { RankPagination } from "@/components/members/rank-pagination"
import { RankSearch } from "@/components/members/rank-search"
import { Button } from "@/components/ui/button"
import { SectionHeading } from "@/components/ui/section-heading"
import { getSessionUser, listArticles, listTags, myArticles } from "@/lib/api/server"
import type { Article, ArticleList, Tag } from "@/lib/api/types"
import { canWrite, tagColor } from "@/lib/articles"
import { cn } from "@/lib/cn"
import { formatNumber } from "@/lib/format"
import { firstParam, parsePage } from "@/lib/members"
import { sessionToken } from "@/lib/session"

export const metadata: Metadata = {
  title: "Articles · SaucisseLand",
  description: "Découvre les articles et actualités de la communauté SaucisseLand.",
}

const LIMIT = 12

function Note({ children }: { children: React.ReactNode }) {
  return (
    <p className="mt-10 mb-0 rounded-2xl border border-line bg-[rgb(19_22_42/0.6)] px-6 py-5 text-muted" role="status">
      {children}
    </p>
  )
}

const href = (tag: string | undefined, search: string | undefined, page = 1) => {
  const qs = new URLSearchParams()
  if (tag) qs.set("tag", tag)
  if (search) qs.set("q", search)
  if (page > 1) qs.set("page", String(page))
  const text = qs.toString()
  return text ? `/articles?${text}` : "/articles"
}

/**
 * Liste des articles publiés (recherche, tag, pagination). Un rédacteur voit aussi ses brouillons
 * (`/articles/mine`, lus avec sa session et jamais mis en cache) et la gestion des tags.
 */
export default async function ArticlesPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>
}) {
  const sp = await searchParams
  const page = parsePage(firstParam(sp.page))
  const tag = firstParam(sp.tag)?.trim() || undefined
  const search = firstParam(sp.q)?.trim() || undefined

  const token = await sessionToken()
  const me = token ? await getSessionUser(token) : null
  const writer = canWrite(me)

  const [list, tags, mine] = await Promise.all([
    listArticles({ page, limit: LIMIT, tag, search }).catch((): ArticleList | null => null),
    listTags().catch((): Tag[] => []),
    writer && token ? myArticles(token).catch((): Article[] => []) : Promise.resolve<Article[]>([]),
  ])
  const drafts = mine.filter(a => !a.published)

  return (
    <main className="relative pt-10 pb-24">
      <div className="relative mx-auto max-w-[1100px] px-6 min-[1100px]:px-10">
        <SectionHeading
          as="h1"
          title="Articles"
          sub="Actualités et textes de la communauté."
          action={
            <div className="flex flex-wrap items-center gap-3">
              <Suspense>
                <RankSearch defaultValue={search ?? ""} placeholder="Rechercher un article…" />
              </Suspense>
              {writer && (
                <Button href="/editeur/nouveau" prefetch={false} size="sm">
                  Nouvel article
                </Button>
              )}
            </div>
          }
        />

        {tags.length > 0 && (
          <nav aria-label="Filtrer par tag" className="mt-8 flex flex-wrap gap-2">
            <Link
              href={href(undefined, search)}
              prefetch={false}
              aria-current={!tag ? "page" : undefined}
              className={cn(
                "rounded-full border px-4 py-1.5 text-sm font-semibold",
                !tag ? "border-violet bg-violet/10 text-violet" : "border-line text-muted hover:border-violet/40 hover:text-fg",
              )}
            >
              Tous
            </Link>
            {tags.map(t => {
              const active = tag === t.slug
              const color = tagColor(t.color)
              return (
                <Link
                  key={t.id}
                  href={href(t.slug, search)}
                  prefetch={false}
                  aria-current={active ? "page" : undefined}
                  className={cn("rounded-full border px-4 py-1.5 text-sm font-semibold", !active && "border-line text-muted hover:text-fg")}
                  style={active ? { borderColor: color, color, backgroundColor: `${color}22` } : undefined}
                >
                  {t.name}
                </Link>
              )
            })}
          </nav>
        )}

        {writer && (
          <div className="mt-6">
            <TagManager initialTags={tags} />
          </div>
        )}

        {drafts.length > 0 && (
          <section aria-labelledby="drafts-title" className="mt-10">
            <h2 id="drafts-title" className="mb-4 flex items-center gap-2 font-display text-lg font-bold">
              Mes brouillons
              <span className="rounded-full bg-white/8 px-2 py-0.5 text-xs font-normal text-muted">{drafts.length}</span>
            </h2>
            <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {drafts.map(a => (
                <ArticleCard key={a.id} article={a} draft />
              ))}
            </div>
          </section>
        )}

        {!list ? (
          <Note>Les articles sont injoignables pour l’instant. Hermes recompte, reviens dans un moment.</Note>
        ) : (
          <>
            {(search || tag) && (
              <p className="mt-8 mb-0 text-sm text-muted">
                {formatNumber(list.total)} article{list.total > 1 ? "s" : ""}
                {search && (
                  <>
                    {" "}
                    pour « <strong className="text-fg">{search}</strong> »
                  </>
                )}
                {tag && (
                  <>
                    {" "}
                    avec le tag <strong className="text-fg">{tags.find(t => t.slug === tag)?.name ?? tag}</strong>
                  </>
                )}
              </p>
            )}
            {list.articles.length === 0 ? (
              <Note>{search ? `Aucun résultat pour « ${search} ».` : "Aucun article publié pour le moment."}</Note>
            ) : (
              <div className="mt-8 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
                {list.articles.map(a => (
                  <ArticleCard key={a.id} article={a} />
                ))}
              </div>
            )}
            <RankPagination
              page={list.page}
              totalPages={Math.ceil(list.total / list.limit)}
              label="Pagination des articles"
              hrefFor={p => href(tag, search, p)}
            />
          </>
        )}
      </div>
    </main>
  )
}
