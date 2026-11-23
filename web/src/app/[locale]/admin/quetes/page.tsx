import { AdminDenied, AdminNote } from "@/components/admin/admin-denied"
import { ActiveQuests } from "@/components/admin/active-quests"
import { QuestLibrary } from "@/components/admin/quest-library"
import { SectionHeading } from "@/components/ui/section-heading"
import { adminGate } from "@/lib/admin-gate"
import { getActiveQuests, getQuestTemplates } from "@/lib/api/server"

export default async function AdminQuestsPage() {
  const gate = await adminGate()
  if (gate.kind !== "ok") return <AdminDenied gate={gate} />
  const [templates, active] = await Promise.all([getQuestTemplates(gate.token), getActiveQuests(gate.token)])

  return (
    <div className="grid gap-8">
      <SectionHeading as="h1" title="Quêtes" sub="Chaque semaine, Hermes tire des quêtes dans la bibliothèque (deux par condition au plus)." />
      <ActiveQuests quests={active} />
      {templates ? (
        <QuestLibrary templates={templates} />
      ) : (
        <AdminNote tone="error">Bibliothèque de quêtes illisible pour l’instant.</AdminNote>
      )}
    </div>
  )
}
