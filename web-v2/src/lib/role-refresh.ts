/**
 * Droits du site réévalués en cours de session (constat I2 de la relecture finale).
 *
 * `isAdmin`/`isRedacteur` sont stockés dans la table `user` et lus par web-api à chaque requête.
 * Calculés seulement à la connexion, ils survivaient au retrait du rôle Discord tant que la
 * session glissante restait active. Ici, avant tout appel à web-api portant une session, les
 * droits plus vieux que `ROLE_TTL_MS` sont recalculés auprès de Discord.
 *
 * Discord injoignable : les droits en base sont conservés (nouvel essai au plus tard dans
 * `RECHECK_MS`). Membre parti du serveur : droits retirés.
 */

export const ROLE_TTL_MS = 10 * 60 * 1000
/** Mémoire locale : au plus une lecture en base par session et par minute. */
export const RECHECK_MS = 60 * 1000

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

  async function run(token: string): Promise<void> {
    try {
      const session = await deps.lookup(token)
      if (!session?.discordId) return
      if (deps.now() - session.checkedAt.getTime() < ROLE_TTL_MS) return
      const roles = await deps.resolve(session.discordId)
      if (roles) await deps.store(session.userId, roles)
    } catch (e) {
      console.error("[auth] réévaluation des droits impossible:", e)
    } finally {
      recent.set(token, deps.now())
    }
  }

  return function refresh(rawToken: string): Promise<void> {
    // BetterAuth ajoute « .signature » au jeton du cookie ; la table `session` stocke le jeton nu.
    let decoded = rawToken
    try {
      decoded = decodeURIComponent(rawToken)
    } catch {}
    const token = decoded.split(".")[0]
    if (!token) return Promise.resolve()
    const last = recent.get(token)
    if (last !== undefined && deps.now() - last < RECHECK_MS) return Promise.resolve()
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
