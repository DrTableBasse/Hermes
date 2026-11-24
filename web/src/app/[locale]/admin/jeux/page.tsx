import { AdminDenied, AdminNote } from "@/components/admin/admin-denied"
import { GamesAdmin } from "@/components/admin/games-admin"
import { SectionHeading } from "@/components/ui/section-heading"
import { adminGate } from "@/lib/admin-gate"
import { getAdminGames, getDiscordChannels, getDiscordRoles } from "@/lib/api/server"

export default async function AdminGamesPage() {
  const gate = await adminGate("games.manage")
  if (gate.kind !== "ok") return <AdminDenied gate={gate} />
  // Rattacher un rôle ou un forum existant est réservé aux admins (web-api refuse sinon) :
  // les listes ne sont lues que pour eux.
  const canAttach = gate.isAdmin
  const [data, roleList, channelList] = await Promise.all([
    getAdminGames(gate.token),
    canAttach ? getDiscordRoles(gate.token) : null,
    canAttach ? getDiscordChannels(gate.token) : null,
  ])
  const forbidden = roleList === "forbidden" || channelList === "forbidden"
  const roles = Array.isArray(roleList) ? roleList : null
  const channels = Array.isArray(channelList) ? channelList : null

  return (
    <div className="grid gap-8">
      <SectionHeading
        as="h1"
        title="Jeux"
        sub="Chaque jeu a son rôle, son forum et sa commande d’appel. Les jeux actifs apparaissent sur l’accueil, dans cet ordre ; un jeu désactivé reste ici."
      />
      {!data ? (
        <AdminNote tone="error">Liste des jeux illisible pour l’instant.</AdminNote>
      ) : (
        <>
          {!canAttach ? (
            <AdminNote>
              Rattacher un rôle ou un forum existant est réservé aux administrateurs : Hermes crée ceux de chaque
              nouveau jeu.
            </AdminNote>
          ) : forbidden ? (
            <AdminNote>
              Votre accès ne couvre pas les listes de rôles et de forums : ils se saisissent par identifiant.
            </AdminNote>
          ) : (
            (!roles || !channels) && data.bot_reachable && <AdminNote>Hermes ne répond pas : rôles et forums se saisissent par identifiant.</AdminNote>
          )}
          {!data.bot_reachable && (
            <AdminNote tone="error">
              Hermes ne répond pas : l’état Discord des jeux est inconnu et la création du rôle, du forum ou de la
              commande échouera tant qu’il ne sera pas revenu.
            </AdminNote>
          )}
          <GamesAdmin games={data.games} roles={roles} channels={channels} canAttach={canAttach} />
        </>
      )}
    </div>
  )
}
