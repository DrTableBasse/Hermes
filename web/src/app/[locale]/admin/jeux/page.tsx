import { AdminDenied, AdminNote } from "@/components/admin/admin-denied"
import { GamesAdmin } from "@/components/admin/games-admin"
import { SectionHeading } from "@/components/ui/section-heading"
import { adminGate } from "@/lib/admin-gate"
import { getAdminGames, getDiscordChannels, getDiscordRoles } from "@/lib/api/server"

export default async function AdminGamesPage() {
  const gate = await adminGate()
  if (gate.kind !== "ok") return <AdminDenied gate={gate} />
  const [games, roles, channels] = await Promise.all([
    getAdminGames(gate.token),
    getDiscordRoles(gate.token),
    getDiscordChannels(gate.token),
  ])

  return (
    <div className="grid gap-8">
      <SectionHeading as="h1" title="Jeux" sub="Les jeux actifs apparaissent sur l’accueil, dans cet ordre. Un jeu désactivé reste ici." />
      {!games ? (
        <AdminNote tone="error">Liste des jeux illisible pour l’instant.</AdminNote>
      ) : (
        <>
          {(!roles || !channels) && <AdminNote>Hermes ne répond pas : rôles et forums se saisissent par identifiant.</AdminNote>}
          <GamesAdmin games={games} roles={roles} channels={channels} />
        </>
      )}
    </div>
  )
}
