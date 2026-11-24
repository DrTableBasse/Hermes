import "server-only"

import { cache } from "react"
import { hasAdminAccess } from "@/lib/admin-sections"
import { getSessionUser } from "@/lib/api/server"
import type { SitePermission } from "@/lib/permissions"
import { sessionToken } from "@/lib/session"

/**
 * Accès à une page de `/admin` :
 * - `ok` : la session porte le droit demandé (`permissions` de `/auth/me`, droits effectifs) ;
 * - `forbidden` : connecté sans ce droit (`permission` : le droit manquant, absent pour le cadre ;
 *   `anyOf` : les droits dont l'un aurait suffi, quand la page en accepte plusieurs) ;
 * - `signin` : aucune session (visiteur) ;
 * - `unavailable` : session illisible (API muette).
 */
export type AdminGate =
  | { kind: "ok"; token: string; permissions: SitePermission[]; isAdmin: boolean }
  | { kind: "forbidden"; permission?: SitePermission; anyOf?: readonly SitePermission[] }
  | { kind: "signin" }
  | { kind: "unavailable" }

const readSession = cache(async () => {
  const token = await sessionToken()
  if (!token) return null
  return { token, me: await getSessionUser(token) }
})

/**
 * Vérifié par le layout (sans argument : au moins une section ouverte) et par chaque page avec le
 * droit de ses routes (le layout n'est pas rejoué à chaque navigation). web-api refuse de toute façon
 * une route admin appelée sans son droit. Une liste de droits : n'importe lequel suffit.
 */
export const adminGate = cache(async (required?: SitePermission | readonly SitePermission[]): Promise<AdminGate> => {
  const session = await readSession()
  if (!session) return { kind: "signin" }
  const { token, me } = session
  if (!me) return { kind: "unavailable" }
  const permissions = me.permissions ?? []
  const anyOf: readonly SitePermission[] | undefined = typeof required === "string" ? [required] : required
  const allowed = anyOf ? anyOf.some(p => permissions.includes(p)) : hasAdminAccess(permissions)
  if (!allowed) {
    if (!anyOf) return { kind: "forbidden" }
    return anyOf.length > 1 ? { kind: "forbidden", permission: anyOf[0], anyOf } : { kind: "forbidden", permission: anyOf[0] }
  }
  return { kind: "ok", token, permissions, isAdmin: me.is_admin === true }
})
