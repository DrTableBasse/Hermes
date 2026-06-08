import type { MetadataRoute } from 'next'

export default function robots(): MetadataRoute.Robots {
  const base = (process.env.NEXT_PUBLIC_APP_URL ?? 'http://localhost:3000').replace(/\/$/, '')
  return {
    rules: [
      {
        userAgent: '*',
        allow: '/',
        disallow: ['/fr/admin', '/en/admin', '/fr/editor', '/en/editor'],
      },
    ],
    sitemap: `${base}/sitemap.xml`,
  }
}
