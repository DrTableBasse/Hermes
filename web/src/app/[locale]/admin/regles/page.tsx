import { AdminDenied, AdminNote } from "@/components/admin/admin-denied"
import { RoleRulesAdmin } from "@/components/admin/role-rules-admin"
import { SectionHeading } from "@/components/ui/section-heading"
import { adminGate } from "@/lib/admin-gate"
import { getAchievementCatalog, getAdminRoles, getGradesFresh, getRoleRules } from "@/lib/api/server"

/** Règles automatiques de rôles (`/admin/role-rules`, droit `roles.manage`). */
export default async function AdminRulesPage() {
  const gate = await adminGate("roles.manage")
  if (gate.kind !== "ok") return <AdminDenied gate={gate} />
  const [rules, roles, catalog, grades] = await Promise.all([
    getRoleRules(gate.token),
    getAdminRoles(gate.token),
    getAchievementCatalog(),
    getGradesFresh(gate.token),
  ])

  return (
    <div className="grid gap-8">
      <SectionHeading
        as="h1"
        title="Règles automatiques"
        sub="Une règle nouvelle ou modifiée reste en « Aperçu » : seuls les membres qui remplissent la condition à un évènement reçoivent le rôle. Elle passe en « Appliquée » après « Voir l’aperçu » puis « Valider »."
      />
      {!rules || !roles ? (
        <AdminNote tone="error">Règles illisibles pour l’instant : le site ou Hermes ne répond pas. Réessaie dans un moment.</AdminNote>
      ) : (
        <RoleRulesAdmin
          initialRules={rules}
          roles={roles.roles}
          achievements={catalog?.achievements ?? []}
          grades={grades ?? []}
          canMemberRoles={gate.permissions.includes("members.roles")}
        />
      )}
    </div>
  )
}
