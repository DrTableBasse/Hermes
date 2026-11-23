/**
 * Contrôle d'origine des requêtes qui modifient des données (constat M4 : CSRF).
 *
 * Le cookie de session est `SameSite=Lax` : il part donc aussi avec un POST émis par une page
 * « same-site » (autre service du même domaine, sous-domaine). Le proxy refuse toute méthode non
 * sûre dont l'`Origin` n'est pas le site lui-même :
 * - `Origin` présente : son hôte doit être celui de l'URL publique configurée
 *   (`NEXT_PUBLIC_APP_URL`, `BETTER_AUTH_URL`) ou celui de la requête (`Host`, posé par le
 *   navigateur et que la page appelante ne choisit pas). L'URL publique couvre le cas d'un proxy
 *   qui réécrit `Host` (Cloudflare Tunnel avec `httpHostHeader`, reverse proxy) ;
 * - `Origin` absente : acceptée seulement si `Sec-Fetch-Site` vaut `same-origin` ou est absent
 *   (client non navigateur : curl, scripts — qui ne portent pas le cookie d'un visiteur).
 *
 * Les URL sont lues au runtime (constat m1) : un accès littéral `process.env.NEXT_PUBLIC_…` est
 * remplacé par sa valeur au build, et le build Docker n'a pas de `.env` — d'où des clés calculées.
 */
import type { HeaderSource } from "./forward"

const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"])

/** Variables portant l'URL publique du site, lues par clé calculée (jamais inlinées). */
const PUBLIC_URL_VARS = ["NEXT_PUBLIC_APP_URL", "BETTER_AUTH_URL"]

type Env = Record<string, string | undefined>

function hostOf(url: string | undefined | null): string | null {
  if (!url) return null
  try {
    return new URL(url).host.toLowerCase()
  } catch {
    return null
  }
}

/** Hôtes publics configurés pour le site (lecture au moment de l'appel). */
export function publicHosts(env: Env = process.env): string[] {
  const hosts: string[] = []
  for (const name of PUBLIC_URL_VARS) {
    const host = hostOf(env[name])
    if (host && !hosts.includes(host)) hosts.push(host)
  }
  return hosts
}

export function isSameOriginRequest(
  method: string,
  headers: HeaderSource,
  env: Env = process.env,
): boolean {
  if (SAFE_METHODS.has(method.toUpperCase())) return true
  const origin = headers.get("origin")
  if (origin === null) {
    const site = headers.get("sec-fetch-site")
    return site === null || site === "same-origin"
  }
  // `Origin: null` (iframe sandbox, redirection, file://) : jamais le site lui-même.
  const originHost = hostOf(origin)
  if (!originHost) return false
  if (publicHosts(env).includes(originHost)) return true
  return headers.get("host")?.toLowerCase() === originHost
}
