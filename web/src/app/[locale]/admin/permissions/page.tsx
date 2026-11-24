import { AdminDenied, AdminNote } from "@/components/admin/admin-denied"
import { CommandPermissions } from "@/components/admin/command-permissions"
import { DiscordPermissionsGrid } from "@/components/admin/discord-permissions-grid"
import { PermissionsTabs } from "@/components/admin/permissions-tabs"
import { SectionHeading } from "@/components/ui/section-heading"
import { adminGate } from "@/lib/admin-gate"
import { getCommandPermissions, getDiscordPermissions } from "@/lib/api/server"

/**
 * Permissions (`/admin/permissions`, droit `permissions.manage`) : permissions Discord des rôles,
 * listes blanches des commandes Hermes ; l'onglet Site renvoie à `/admin/acces` (même droit).
 */
export default async function AdminPermissionsPage() {
  const gate = await adminGate("permissions.manage")
  if (gate.kind !== "ok") return <AdminDenied gate={gate} />
  const [discord, commands] = await Promise.all([getDiscordPermissions(gate.token), getCommandPermissions(gate.token)])

  return (
    <div className="grid gap-8">
      <SectionHeading
        as="h1"
        title="Permissions"
        sub="Ce que chaque rôle peut faire sur Discord et avec les commandes d’Hermes. Vous ne modifiez que les rôles sous le vôtre, et seulement les permissions que vous avez."
      />
      <PermissionsTabs
        siteHref="/admin/acces"
        tabs={[
          {
            key: "discord",
            label: "Discord",
            panel: discord ? (
              <DiscordPermissionsGrid initial={discord} />
            ) : (
              <AdminNote tone="error">Permissions Discord illisibles pour l’instant : le site ou Hermes ne répond pas. Réessaie dans un moment.</AdminNote>
            ),
          },
          {
            key: "hermes",
            label: "Hermes",
            panel: commands ? (
              <CommandPermissions initial={commands} />
            ) : (
              <AdminNote tone="error">Commandes illisibles pour l’instant : le site ou Hermes ne répond pas. Réessaie dans un moment.</AdminNote>
            ),
          },
        ]}
      />
    </div>
  )
}
