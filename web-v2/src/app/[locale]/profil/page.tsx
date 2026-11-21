import type { Metadata } from "next"
import { StaffProfileForm } from "@/components/staff/staff-profile-form"
import { SectionHeading } from "@/components/ui/section-heading"
import { getGames, getSessionUser, getStaff } from "@/lib/api/server"
import { sessionToken } from "@/lib/session"

export const metadata: Metadata = {
  title: "Profil · SaucisseLand",
}

function Note({ children }: { children: React.ReactNode }) {
  return (
    <p className="mt-8 mb-0 rounded-2xl border border-line bg-[rgb(19_22_42/0.6)] px-6 py-5 text-muted" role="status">
      {children}
    </p>
  )
}

/**
 * Profil, version minimale : édition de sa carte de l'état-major pour un membre du staff. La page
 * complète (statistiques, succès…) viendra plus tard. `src/proxy.ts` renvoie déjà à l'accueil sans session.
 */
export default async function ProfilePage() {
  const token = await sessionToken()
  const [me, staff, games] = token
    ? await Promise.all([getSessionUser(token), getStaff(token), getGames()])
    : [null, null, null]
  const mine = me && staff ? staff.staff.find(m => m.id === me.user_id) : undefined

  return (
    <main className="relative pt-10 pb-24">
      <div className="relative mx-auto max-w-[1440px] px-6 min-[1100px]:px-20">
        <SectionHeading as="h1" title="Ton profil" />
        {/* Liste périmée : phrase et jeux peuvent y être vides (base illisible). Préremplir le formulaire
            avec ce vide ferait écraser le vrai profil au premier « Enregistrer » : pas de formulaire. */}
        {me && staff?.stale ? (
          <Note>Hermes est injoignable pour l’instant, ta carte ne peut pas être modifiée. Réessaie plus tard.</Note>
        ) : mine ? (
          <section
            aria-labelledby="staff-card-title"
            className="mt-10 max-w-[760px] rounded-[22px] border border-white/9 bg-[rgb(19_22_42/0.9)] p-7"
          >
            <h2 id="staff-card-title" className="m-0 font-display text-2xl font-bold">
              Ta carte de l’état-major
            </h2>
            <p className="mt-2 mb-7 text-muted">
              Ce que les recrues voient de toi sur la page de l’état-major. Ton rôle et ton grade viennent du Discord.
            </p>
            {/* Liste périmée (base illisible) : vide, elle ferait croire qu'aucun jeu n'existe. */}
            <StaffProfileForm motto={mine.motto} selected={mine.games} games={games && !games.stale ? games.games : null} />
          </section>
        ) : !me || !staff ? (
          <Note>Ton profil est injoignable pour l’instant. Reviens dans un moment.</Note>
        ) : (
          <Note>Ta page de profil arrive bientôt sur ce site.</Note>
        )}
      </div>
    </main>
  )
}
