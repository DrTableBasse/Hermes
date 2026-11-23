/**
 * Règles communes aux deux chemins vers web-api : le rendu serveur (`server.ts`) et la route
 * proxy du navigateur (`app/api/proxy/[...path]/route.ts`). Une seule implémentation par règle.
 */

/** Lecture d'en-têtes : `Headers` (fetch, `next/headers`) ou équivalent. */
export interface HeaderSource {
  get(name: string): string | null
}

/**
 * IP du visiteur, pour le limiteur de web-api (`X-Client-IP`). On ne relaie jamais un
 * `X-Client-IP` venu du navigateur : on le reconstruit. `X-Real-IP` est posé par le reverse proxy
 * (Nginx Proxy Manager) ; à défaut, la dernière entrée de `X-Forwarded-For`, la seule ajoutée par lui.
 */
export function clientIp(headers: HeaderSource): string | null {
  const real = headers.get("x-real-ip")?.trim()
  if (real) return real
  const last = headers.get("x-forwarded-for")?.split(",").pop()?.trim()
  return last || null
}

// En HTTPS, BetterAuth préfixe son cookie par `__Secure-` (même liste que `src/proxy.ts`).
export const SESSION_COOKIES = ["better-auth.session_token", "__Secure-better-auth.session_token"]

/** Jeton de session lu dans un en-tête `Cookie` brut ; `null` sans session. */
export function sessionFromCookieHeader(cookieHeader: string | null): string | null {
  if (!cookieHeader) return null
  const jar = new Map<string, string>()
  for (const part of cookieHeader.split(";")) {
    const eq = part.indexOf("=")
    if (eq > 0) jar.set(part.slice(0, eq).trim(), part.slice(eq + 1).trim())
  }
  for (const name of SESSION_COOKIES) {
    const value = jar.get(name)
    if (value) return value
  }
  return null
}

/** web-api ne lit que ce nom de cookie, quel que soit le préfixe posé par BetterAuth. */
export const sessionCookie = (token: string) => `better-auth.session_token=${token}`

/** Budget de temps d'une lecture du rendu serveur : au-delà, la section passe en état dégradé. */
export const SSR_TIMEOUT_MS = 3000

/** Budget de temps d'une requête du navigateur. */
export const PROXY_TIMEOUT_MS = 15000

/** Envoi de fichier (multipart, jusqu'à 10 Mo) : le délai couvre aussi la montée du corps, d'où 2 min. */
export const UPLOAD_TIMEOUT_MS = 120_000

/** Délai d'une requête relayée selon son type de corps. */
export function proxyTimeoutFor(contentType: string | null): number {
  return contentType?.toLowerCase().startsWith("multipart/form-data") ? UPLOAD_TIMEOUT_MS : PROXY_TIMEOUT_MS
}
