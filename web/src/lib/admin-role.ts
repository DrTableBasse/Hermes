import "server-only"
import { pool } from "./db"

/** Rôle par identifiant (réglage en base) ou par nom (repli sur l'environnement). */
export type RoleRef = { id: string } | { name: string }

export const ADMIN_ROLE_NAME = process.env.ADMIN_ROLE_NAME ?? "Administration"

/**
 * Rôle d'administration en vigueur : réglage `admin_role` (identifiant), sinon le nom de
 * l'environnement. `null` si `bot_settings` est illisible. Module sans BetterAuth : la page
 * /admin/acces l'importe sans instancier l'authentification au build.
 */
export async function readAdminRoleRef(): Promise<RoleRef | null> {
  try {
    const res = await pool.query<{ value: string | null }>(
      `SELECT value FROM bot_settings WHERE key = 'admin_role'`
    )
    const id = res.rows[0]?.value
    return id ? { id } : { name: ADMIN_ROLE_NAME }
  } catch (e) {
    console.error("[auth] lecture de bot_settings impossible, repli sur l'environnement:", e)
    return null
  }
}
