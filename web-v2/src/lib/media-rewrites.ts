type Rewrites = Array<{ source: string; destination: string }>

const DEFAULT_API = "http://web-api:8000"

/**
 * Relaie `/media/*` (captures de la galerie, visuels des jeux) vers web-api, qui sert le volume
 * `media_data` en statique. Seul ce préfixe est relayé : le reste de web-api reste joignable
 * uniquement par `/api/proxy`. Le navigateur voit une URL de même origine, donc la CSP
 * `img-src 'self'` s'applique telle quelle.
 *
 * Évalué au build (`output: 'standalone'` fige les rewrites) : sans variable, la valeur par défaut
 * est celle du réseau Docker.
 */
export function mediaRewrites(apiUrl: string | undefined = process.env.WEB_API_INTERNAL_URL): Rewrites {
  const base = (apiUrl || DEFAULT_API).replace(/\/+$/, "")
  return [{ source: "/media/:path*", destination: `${base}/media/:path*` }]
}
