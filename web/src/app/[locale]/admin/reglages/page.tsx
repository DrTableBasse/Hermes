import { AdminDenied, AdminNote } from "@/components/admin/admin-denied"
import { SettingsPanel } from "@/components/admin/settings-panel"
import { SectionHeading } from "@/components/ui/section-heading"
import { adminGate } from "@/lib/admin-gate"
import { getAdminSettings, getDiscordChannels, getDiscordRoles } from "@/lib/api/server"

export default async function AdminSettingsPage() {
  const gate = await adminGate("settings.manage")
  if (gate.kind !== "ok") return <AdminDenied gate={gate} />
  const [settings, channels, roles] = await Promise.all([
    getAdminSettings(gate.token),
    getDiscordChannels(gate.token),
    getDiscordRoles(gate.token),
  ])

  return (
    <div className="grid gap-8">
      <SectionHeading
        as="h1"
        title="Réglages"
        sub="Salons, rôles et liens que Hermes et le site utilisent. Un champ effacé retombe sur sa valeur par défaut."
      />
      {!settings ? (
        <AdminNote tone="error">Réglages illisibles pour l’instant : le site ne répond pas. Réessaie dans un moment.</AdminNote>
      ) : (
        <>
          {(!channels || !roles) && (
            <AdminNote tone="error">
              Hermes ne répond pas : les listes de salons et de rôles sont indisponibles. Les identifiants restent
              modifiables à la main.
            </AdminNote>
          )}
          <SettingsPanel groups={settings.groups} channels={channels} roles={roles} />
        </>
      )}
    </div>
  )
}
