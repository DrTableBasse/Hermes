import { AdminDenied, AdminNote } from "@/components/admin/admin-denied"
import { AnalyticsDashboard } from "@/components/admin/analytics-dashboard"
import { SectionHeading } from "@/components/ui/section-heading"
import { adminGate } from "@/lib/admin-gate"
import { getAnalytics } from "@/lib/api/server"

export default async function AdminAnalyticsPage() {
  const gate = await adminGate("analytics.view")
  if (gate.kind !== "ok") return <AdminDenied gate={gate} />
  const data = await getAnalytics(gate.token)

  return (
    <div className="grid gap-8">
      <SectionHeading as="h1" title="Analytique" sub="Chiffres lus à l’ouverture de la page." />
      {data ? <AnalyticsDashboard data={data} /> : <AdminNote tone="error">Analytique indisponible pour l’instant.</AdminNote>}
    </div>
  )
}
