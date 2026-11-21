import type { MetadataRoute } from "next"
import { isIndexable, PRIVATE_PATHS, siteUrl } from "@/lib/site"

// Lu à chaque requête : SITE_INDEXABLE et l’URL du site viennent de l’environnement du conteneur.
export const dynamic = "force-dynamic"

export default function robots(): MetadataRoute.Robots {
  if (!isIndexable()) return { rules: { userAgent: "*", disallow: "/" } }
  return {
    rules: { userAgent: "*", allow: "/", disallow: [...PRIVATE_PATHS] },
    sitemap: `${siteUrl()}/sitemap.xml`,
  }
}
