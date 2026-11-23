import { AdminDenied, AdminNote } from "@/components/admin/admin-denied"
import { CommandsPanel } from "@/components/admin/commands-panel"
import { SectionHeading } from "@/components/ui/section-heading"
import { adminGate } from "@/lib/admin-gate"
import { getAdminCommands } from "@/lib/api/server"

export default async function AdminCommandsPage() {
  const gate = await adminGate("settings.manage")
  if (gate.kind !== "ok") return <AdminDenied gate={gate} />
  const data = await getAdminCommands(gate.token)

  return (
    <div className="grid gap-8">
      <SectionHeading as="h1" title="Commandes" sub="Une commande coupée répond « désactivée » sur Discord." />
      {!data ? (
        <AdminNote tone="error">Hermes ne répond pas : la liste des commandes est indisponible.</AdminNote>
      ) : Object.keys(data.commands).length === 0 ? (
        <AdminNote>Aucune commande enregistrée.</AdminNote>
      ) : (
        <CommandsPanel commands={data.commands} descriptions={data.descriptions ?? {}} />
      )}
    </div>
  )
}
