import type { MetadataRoute } from "next"
import { listArticles } from "@/lib/api/server"
import type { Article } from "@/lib/api/types"
import { isIndexable, PUBLIC_PATHS, siteUrl } from "@/lib/site"

const PER_PAGE = 100
const MAX_PAGES = 20

/** Articles publiés, page par page ; API muette → liste vide (le sitemap garde les pages fixes). */
async function publishedArticles(): Promise<Article[]> {
  const found: Article[] = []
  try {
    for (let page = 1; page <= MAX_PAGES; page++) {
      const list = await listArticles({ page, limit: PER_PAGE })
      found.push(...list.articles)
      if (page * list.limit >= list.total || list.articles.length === 0) break
    }
  } catch {
    // On sert ce qu'on a déjà lu.
  }
  return found
}

// Lu à chaque requête : URL du site, SITE_INDEXABLE et liste d'articles ne sont pas figés au build.
export const dynamic = "force-dynamic"

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  // Site non indexable : rien à annoncer aux moteurs.
  if (!isIndexable()) return []
  const base = siteUrl()
  const pages: MetadataRoute.Sitemap = PUBLIC_PATHS.map(path => ({ url: path === "/" ? base : `${base}${path}` }))
  const articles = (await publishedArticles()).filter(a => a.published)
  return [
    ...pages,
    ...articles.map(a => ({ url: `${base}/articles/${encodeURIComponent(a.slug)}`, lastModified: new Date(a.updated_at) })),
  ]
}
