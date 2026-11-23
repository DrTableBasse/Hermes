/**
 * Droits du site réévalués en cours de session (constat I2 de la relecture finale).
 *
 * `isAdmin`/`isRedacteur` sont stockés dans la table `user` et lus par web-api à chaque requête.
 * Calculés seulement à la connexion, ils survivaient au retrait du rôle Discord tant que la
 * session glissante restait active. Ici, à chaque appel à web-api portant une session, les
 * droits plus vieux que `ROLE_TTL_MS` sont recalculés auprès de Discord, en arrière-plan : la
 * requête n'attend jamais Discord, le retrait de droits s'applique à la requête suivante.
 *
 * Discord injoignable : les droits en base sont conservés et plus aucune session ne rappelle
 * Discord pendant `RECHECK_MS`. Membre parti du serveur : droits retirés.
 */

export const ROLE_TTL_MS = 10 * 60 * 1000
/** Mémoire locale : au plus une lecture en base par session et par minute. */
export const RECHECK_MS = 60 * 1000

/** Sessions mémorisées au plus (constat M1) : au-delà, les plus anciennes sont oubliées. */
export const MAX_RECENT = 10_000

/**
 * Forme d'un jeton de session BetterAuth (`generateId(32)` : alphanumérique). Un cookie qui n'a
 * pas cette forme ne déclenche ni requête SQL ni entrée en mémoire (constat M1).
 */
const TOKEN_RE = /^[A-Za-z0-9_-]{16,128}$/

export type StaffRoles = [isAdmin: boolean, isRedacteur: boolean]

export interface SessionRoles {
  userId: string
  discordId: string | null
  checkedAt: Date
}

export interface RoleRefreshDeps {
  /** Session valide → utilisateur et date du dernier calcul des droits ; `null` sinon. */
  lookup(token: string): Promise<SessionRoles | null>
  /** Rôles Discord ; `null` : Discord injoignable (erreur réseau, 429, 5xx…). */
  resolve(discordId: string): Promise<StaffRoles | null>
  store(userId: string, roles: StaffRoles): Promise<void>
  now(): number
}

export function createRoleRefresher(deps: RoleRefreshDeps) {
  const recent = new Map<string, number>()
  const inflight = new Map<string, Promise<void>>()
  /** Discord injoignable : pas de nouvel appel, toutes sessions confondues, avant cette date. */
  let discordRetryAt = 0

  async function run(token: string): Promise<void> {
    try {
      const session = await deps.lookup(token)
      if (!session?.discordId) return
      if (deps.now() - session.checkedAt.getTime() < ROLE_TTL_MS) return
      if (deps.now() < discordRetryAt) return
      const roles = await deps.resolve(session.discordId)
      if (roles) await deps.store(session.userId, roles)
      else discordRetryAt = deps.now() + RECHECK_MS
    } catch (e) {
      console.error("[auth] réévaluation des droits impossible:", e)
    } finally {
      remember(token)
    }
  }

  /** Mémorise la date de vérification ; purge les entrées expirées puis, au besoin, les plus anciennes. */
  function remember(token: string): void {
    const now = deps.now()
    recent.delete(token)
    if (recent.size >= MAX_RECENT) {
      for (const [key, at] of recent) if (now - at >= RECHECK_MS) recent.delete(key)
      // Ordre d'insertion = ordre de vérification : on retire les plus anciennes.
      for (const key of recent.keys()) {
        if (recent.size < MAX_RECENT) break
        recent.delete(key)
      }
    }
    recent.set(token, now)
  }

  return function refresh(rawToken: string): Promise<void> {
    // BetterAuth ajoute « .signature » au jeton du cookie ; la table `session` stocke le jeton nu.
    let decoded = rawToken
    try {
      decoded = decodeURIComponent(rawToken)
    } catch {}
    const token = decoded.split(".")[0]
    if (!TOKEN_RE.test(token)) return Promise.resolve()
    const last = recent.get(token)
    if (last !== undefined) {
      if (deps.now() - last < RECHECK_MS) return Promise.resolve()
      recent.delete(token)
    }
    const pending = inflight.get(token)
    if (pending) return pending
    const p = run(token).finally(() => inflight.delete(token))
    inflight.set(token, p)
    return p
  }
}

let defaultRefresher: ((token: string) => Promise<void>) | null = null

/** Réévalue les droits de la session si besoin ; ne lève jamais d'erreur. */
export async function refreshRolesIfStale(token: string): Promise<void> {
  if (!defaultRefresher) {
    // Import tardif : BetterAuth et le pool PostgreSQL ne sont chargés qu'à l'usage.
    const { roleRefreshDeps } = await import("@/lib/auth")
    defaultRefresher = createRoleRefresher(roleRefreshDeps)
  }
  return defaultRefresher(token)
}

/** Lance la réévaluation sans l'attendre : la requête en cours ne dépend jamais de Discord. */
export function refreshRolesInBackground(token: string): void {
  refreshRolesIfStale(token).catch(e => console.error("[auth] réévaluation des droits impossible:", e))
}
