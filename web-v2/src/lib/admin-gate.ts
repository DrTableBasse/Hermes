import "server-only"

import { cache } from "react"
import { getSessionUser } from "@/lib/api/server"
import { sessionToken } from "@/lib/session"

/**
 * Accès à `/admin` : `ok` (session administrateur, `isAdmin` de la session BetterAuth lu par `/auth/me`),
 * `forbidden` (connecté sans droit, ou sans session) ou `unavailable` (session illisible : API muette).
 */
export type AdminGate = { kind: "ok"; token: string } | { kind: "forbidden" } | { kind: "unavailable" }

/** Vérifié par le layout et par chaque page (le layout n'est pas rejoué à chaque navigation). */
export const adminGate = cache(async (): Promise<AdminGate> => {
  const token = await sessionToken()
  if (!token) return { kind: "forbidden" }
  const me = await getSessionUser(token)
  if (!me) return { kind: "unavailable" }
  return me.is_admin ? { kind: "ok", token } : { kind: "forbidden" }
})
