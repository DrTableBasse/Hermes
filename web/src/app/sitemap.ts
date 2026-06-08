import type { MetadataRoute } from 'next'

const LOCALES = ['fr', 'en'] as const
const STATIC_ROUTES = [
  { path: '',             priority: 1.0, changeFreq: 'daily'  },
  { path: '/articles',    priority: 0.9, changeFreq: 'daily'  },
  { path: '/leaderboard', priority: 0.7, changeFreq: 'hourly' },
  { path: '/quests',      priority: 0.6, changeFreq: 'weekly' },
] as const

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const base = (process.env.NEXT_PUBLIC_APP_URL ?? 'http://localhost:3000').replace(/\/$/, '')

  const staticEntries: MetadataRoute.Sitemap = LOCALES.flatMap(locale =>
    STATIC_ROUTES.map(r => ({
      url:             `${base}/${locale}${r.path}`,
      lastModified:    new Date(),
      changeFrequency: r.changeFreq as MetadataRoute.Sitemap[number]['changeFrequency'],
      priority:        r.priority,
    }))
  )

  let articleEntries: MetadataRoute.Sitemap = []
  try {
    const WEB_API = process.env.WEB_API_INTERNAL_URL ?? 'http://web-api:8000'
    const res = await fetch(`${WEB_API}/articles?limit=200&page=1`, { cache: 'no-store' })
    if (res.ok) {
      const data = await res.json()
      const articles: { slug: string; updated_at?: string; created_at: string }[] =
        data.articles ?? []
      articleEntries = LOCALES.flatMap(locale =>
        articles.map(a => ({
          url:             `${base}/${locale}/articles/${a.slug}`,
          lastModified:    new Date(a.updated_at ?? a.created_at),
          changeFrequency: 'weekly' as const,
          priority:        0.6,
        }))
      )
    }
  } catch {}

  return [...staticEntries, ...articleEntries]
}
