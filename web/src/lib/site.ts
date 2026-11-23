/** URL publique du site et règle d'indexation (robots, sitemap, métadonnées, en-tête). */

const FALLBACK_URL = "http://localhost:3000"

/** URL de base sans barre finale, lue sur `NEXT_PUBLIC_APP_URL` puis `BETTER_AUTH_URL`. */
export function siteUrl(env: NodeJS.ProcessEnv = process.env): string {
  const raw = env.NEXT_PUBLIC_APP_URL || env.BETTER_AUTH_URL || FALLBACK_URL
  return raw.replace(/\/+$/, "")
}

/**
 * Indexation autorisée : fail-closed. Seule `SITE_INDEXABLE=true` (lue au runtime, jamais déduite de
 * l'URL ni du port) ouvre le site aux moteurs ; absente ou autre valeur, tout reste interdit.
 */
export function isIndexable(env: NodeJS.ProcessEnv = process.env): boolean {
  return env.SITE_INDEXABLE === "true"
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
