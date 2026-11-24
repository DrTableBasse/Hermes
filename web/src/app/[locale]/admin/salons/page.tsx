import { AdminDenied, AdminNote } from "@/components/admin/admin-denied"
import { ChannelsAdmin } from "@/components/admin/channels-admin"
import { SectionHeading } from "@/components/ui/section-heading"
import { adminGate } from "@/lib/admin-gate"
import { getAdminChannels } from "@/lib/api/server"

/** Salons du serveur (`/admin/salons`, `channels.manage`) : arborescence et modèles d'accès. */
export default async function AdminChannelsPage() {
  const gate = await adminGate("channels.manage")
  if (gate.kind !== "ok") return <AdminDenied gate={gate} />
  const data = await getAdminChannels(gate.token)

  return (
    <div className="grid gap-8">
      <SectionHeading
        as="h1"
        title="Salons"
        sub="Seuls les salons que vous voyez dans Discord sont gérables. Un modèle d’accès s’applique après un aperçu des surcharges changées ; supprimer un salon demande de retaper son nom."
      />
      {!data ? (
        <AdminNote tone="error">Salons illisibles pour l’instant : le site ou Hermes ne répond pas. Réessaie dans un moment.</AdminNote>
      ) : (
        <ChannelsAdmin initial={data} />
      )}
    </div>
  )
}
