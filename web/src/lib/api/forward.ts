/**
 * Règles communes aux deux chemins vers web-api : le rendu serveur (`server.ts`) et la route
 * proxy du navigateur (`app/api/proxy/[...path]/route.ts`). Une seule implémentation par règle.
 */

/** Lecture d'en-têtes : `Headers` (fetch, `next/headers`) ou équivalent. */
export interface HeaderSource {
  get(name: string): string | null
}

/** Posé par `runtime/client-ip.cjs` quand il intercepte les requêtes avant Next. */
export const CLIENT_IP_MARKER = "HERMES_CLIENT_IP_PRELOAD"

/**
 * IP du visiteur, pour le limiteur de web-api (`X-Client-IP`).
 *
 * Elle n'est jamais lue dans un en-tête choisi par le client (`X-Real-IP`, `X-Forwarded-For` :
 * constat I1). `runtime/client-ip.cjs`, chargé avant Next, écrase `x-client-ip` sur chaque requête
 * entrante avec l'IP de la socket, ou l'en-tête `TRUSTED_IP_HEADER` posé par le proxy de confiance.
 * Sans ce module (marqueur absent : `next dev`, tests), rien n'est relayé et web-api compte la
 * requête sous l'IP du conteneur `web`.
 */
export function clientIp(headers: HeaderSource, env: Record<string, string | undefined> = process.env): string | null {
  if (!env[CLIENT_IP_MARKER]) return null
  return headers.get("x-client-ip")?.trim() || null
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
