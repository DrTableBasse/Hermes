import { AccessGrid } from "@/components/admin/access-grid"
import { AdminDenied, AdminNote } from "@/components/admin/admin-denied"
import { SectionHeading } from "@/components/ui/section-heading"
import { adminGate } from "@/lib/admin-gate"
import { ADMIN_ROLE_NAME, readAdminRoleRef } from "@/lib/admin-role"
import { getAdminAccess } from "@/lib/api/server"
import type { AccessOverview } from "@/lib/api/types"

/** « vous : <rôle>, position N » : rôle le plus haut de l'acteur, d'après sa position Discord. */
function actorLabel({ roles, actor }: AccessOverview): string {
  if (actor.is_owner) return "vous : propriétaire du serveur"
  if (actor.top_position <= 0) return "vous : aucun rôle sur le serveur"
  const top = roles.find(r => r.position === actor.top_position)
  return `vous : ${top ? `${top.name}, ` : ""}position ${actor.top_position}`
}

/** Droits d'accès au site, rôle par rôle (`GET/PUT /admin/access`, droit `permissions.manage`). */
export default async function AdminAccessPage() {
  const gate = await adminGate("permissions.manage")
  if (gate.kind !== "ok") return <AdminDenied gate={gate} />
  const [data, storedRole] = await Promise.all([getAdminAccess(gate.token), readAdminRoleRef()])
  // Réglage illisible : même repli que l'authentification (nom de l'environnement).
  const adminRole = storedRole ?? { name: ADMIN_ROLE_NAME }
  const adminRoleId = !data
    ? null
    : "id" in adminRole
      ? adminRole.id
      : (data.roles.find(r => r.name === adminRole.name)?.id ?? null)

  return (
    <div className="grid gap-8">
      <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-2">
        <SectionHeading
          as="h1"
          title="Accès"
          sub="Ce que chaque rôle Discord peut faire sur le site. Vous ne modifiez que les rôles sous le vôtre, et seulement les droits que vous avez."
        />
        {data && <p className="m-0 text-sm text-muted">{actorLabel(data)}</p>}
      </div>
      {!data ? (
        <AdminNote tone="error">Accès illisibles pour l’instant : le site ou Hermes ne répond pas. Réessaie dans un moment.</AdminNote>
      ) : (
        <>
          <AdminNote>
            Un changement prend effet sous 10 minutes pour les membres concernés, ou dès leur prochaine connexion.
          </AdminNote>
          <AccessGrid roles={data.roles} actor={data.actor} adminRoleId={adminRoleId} />
        </>
      )}
    </div>
  )
}
