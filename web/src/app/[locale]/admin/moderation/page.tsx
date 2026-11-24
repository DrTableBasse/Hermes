import { AdminDenied } from "@/components/admin/admin-denied"
import { ModerationPanel } from "@/components/admin/moderation-panel"
import { SectionHeading } from "@/components/ui/section-heading"
import { adminGate } from "@/lib/admin-gate"

export default async function AdminModerationPage() {
  const gate = await adminGate("moderation.view")
  if (gate.kind !== "ok") return <AdminDenied gate={gate} />
  return (
    <div className="grid gap-8">
      <SectionHeading
        as="h1"
        title="Modération"
        sub="Expulsion, bannissement et exclusion demandent une confirmation. Chaque action est journalisée."
      />
      <ModerationPanel
        canAct={gate.permissions.includes("moderation.act")}
        canManageRoles={gate.permissions.includes("members.roles")}
      />
    </div>
  )
}
