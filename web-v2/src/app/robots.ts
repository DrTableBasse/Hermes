import type { MetadataRoute } from "next"
import { isStaging, PRIVATE_PATHS, siteUrl } from "@/lib/site"

// Lu à chaque requête : l'URL du site vient de l'environnement du conteneur, pas de celui du build.
export const dynamic = "force-dynamic"

export default function robots(): MetadataRoute.Robots {
  if (isStaging()) return { rules: { userAgent: "*", disallow: "/" } }
  return {
    rules: { userAgent: "*", allow: "/", disallow: [...PRIVATE_PATHS] },
    sitemap: `${siteUrl()}/sitemap.xml`,
  }
}
