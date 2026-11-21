/** URL publique du site et règle d'indexation (robots, sitemap, métadonnées). */

const FALLBACK_URL = "http://localhost:3002"

/** URL de base sans barre finale, lue sur `NEXT_PUBLIC_APP_URL` puis `BETTER_AUTH_URL`. */
export function siteUrl(env: NodeJS.ProcessEnv = process.env): string {
  const raw = env.NEXT_PUBLIC_APP_URL || env.BETTER_AUTH_URL || FALLBACK_URL
  return raw.replace(/\/+$/, "")
}

/**
 * Vrai tant que le site n'est pas servi sur son URL de production : tout est alors interdit aux robots.
 *
 * Le conteneur reçoit `NEXT_PUBLIC_APP_URL = WEB_V2_URL` (compose.yml) : comparer les deux valeurs
 * interdirait donc toujours tout, même en production. Seul le port de préproduction (:3002) discrimine.
 */
export function isStaging(env: NodeJS.ProcessEnv = process.env): boolean {
  return [env.NEXT_PUBLIC_APP_URL, env.BETTER_AUTH_URL, siteUrl(env)].some(url => !!url && url.includes(":3002"))
}

/** Pages publiques du site, hors articles (relatives à la racine). */
export const PUBLIC_PATHS = [
  "/",
  "/progression",
  "/hermes",
  "/galerie",
  "/etat-major",
  "/classement",
  "/top-semaine",
  "/articles",
  "/reglement",
  "/mentions-legales",
] as const

/** Zones privées : jamais indexées. */
export const PRIVATE_PATHS = ["/admin", "/profil", "/editeur", "/quetes", "/tickets"] as const
