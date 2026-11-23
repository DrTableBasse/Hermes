/**
 * Contrôle d'origine des requêtes qui modifient des données (constat M4 : CSRF).
 *
 * Le cookie de session est `SameSite=Lax` : il part donc aussi avec un POST émis par une page
 * « same-site » (autre service du même domaine, sous-domaine). Le proxy refuse toute méthode non
 * sûre dont l'`Origin` n'est pas le site lui-même :
 * - `Origin` présente : son hôte doit être celui de la requête (`Host`, posé par le navigateur et
 *   que la page appelante ne choisit pas) ou celui de `NEXT_PUBLIC_APP_URL` ;
 * - `Origin` absente : acceptée seulement si `Sec-Fetch-Site` vaut `same-origin` ou est absent
 *   (client non navigateur : curl, scripts — qui ne portent pas le cookie d'un visiteur).
 */
import type { HeaderSource } from "./forward"

const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"])

function hostOf(url: string | undefined | null): string | null {
  if (!url) return null
  try {
    return new URL(url).host.toLowerCase()
  } catch {
    return null
  }
}

export function isSameOriginRequest(
  method: string,
  headers: HeaderSource,
  appUrl: string | undefined = process.env.NEXT_PUBLIC_APP_URL,
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
  const allowed = [headers.get("host")?.toLowerCase() ?? null, hostOf(appUrl)]
  return allowed.includes(originHost)
}
