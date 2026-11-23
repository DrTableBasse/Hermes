import { AdminDenied, AdminNote } from "@/components/admin/admin-denied"
import { StaffEditor } from "@/components/admin/staff-editor"
import { SectionHeading } from "@/components/ui/section-heading"
import { adminGate } from "@/lib/admin-gate"
import { getGames, getStaff } from "@/lib/api/server"

export default async function AdminStaffPage() {
  const gate = await adminGate("content.edit")
  if (gate.kind !== "ok") return <AdminDenied gate={gate} />
  const [staff, games] = await Promise.all([getStaff(gate.token), getGames()])

  return (
    <div className="grid gap-8">
      <SectionHeading
        as="h1"
        title="État-major"
        sub="La liste suit les rôles Discord d’administration et de modération ; ici, la phrase et les jeux de chaque carte."
      />
      {!staff ? (
        <AdminNote tone="error">État-major illisible pour l’instant.</AdminNote>
      ) : (
        <>
          {staff.stale && <AdminNote>Liste peut-être incomplète : Hermes ne répond pas, dernière version connue affichée.</AdminNote>}
          <StaffEditor staff={staff.staff} games={games && !games.stale ? games.games : null} />
        </>
      )}
    </div>
  )
}
