import { AdminDenied, AdminNote } from "@/components/admin/admin-denied"
import { RolesAdmin } from "@/components/admin/roles-admin"
import { SectionHeading } from "@/components/ui/section-heading"
import { adminGate } from "@/lib/admin-gate"
import { getAdminRoles } from "@/lib/api/server"

/**
 * Rôles du serveur (`/admin/roles`) : gestion avec `roles.manage`, attribution en lot avec
 * `members.roles` ; l'un des deux ouvre la page (R14).
 */
export default async function AdminRolesPage() {
  const gate = await adminGate(["roles.manage", "members.roles"])
  if (gate.kind !== "ok") return <AdminDenied gate={gate} />
  const data = await getAdminRoles(gate.token)

  return (
    <div className="grid gap-8">
      <SectionHeading
        as="h1"
        title="Rôles"
        sub="Vous ne gérez que les rôles sous le vôtre et sous celui d’Hermes. Supprimer un rôle ou l’attribuer en lot demande de confirmer le nombre de membres concernés."
      />
      {!data ? (
        <AdminNote tone="error">Rôles illisibles pour l’instant : le site ou Hermes ne répond pas. Réessaie dans un moment.</AdminNote>
      ) : (
        <RolesAdmin
          initial={data}
          canManage={gate.permissions.includes("roles.manage")}
          canBulk={gate.permissions.includes("members.roles")}
        />
      )}
    </div>
  )
}
