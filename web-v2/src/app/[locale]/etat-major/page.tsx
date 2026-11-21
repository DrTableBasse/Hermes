import type { Metadata } from "next"
import { StaffCard } from "@/components/staff/staff-card"
import { SectionHeading } from "@/components/ui/section-heading"
import { getGames, getPublicSettings, getStaff } from "@/lib/api/server"
import type { Game } from "@/lib/api/types"

export const metadata: Metadata = {
  title: "L’état-major · SaucisseLand",
  description: "Les gradés qui font tourner la caserne SaucisseLand, et comment les joindre par ticket.",
}

function Note({ children, status }: { children: React.ReactNode; status?: boolean }) {
  return (
    <p
      className="mt-8 mb-0 rounded-2xl border border-line bg-[rgb(19_22_42/0.6)] px-6 py-5 text-muted"
      role={status ? "status" : undefined}
    >
      {children}
    </p>
  )
}

export default async function StaffPage() {
  const [staff, games, settings] = await Promise.all([getStaff(), getGames(), getPublicSettings()])
  const members = staff?.staff ?? []
  const gamesByKey = new Map<string, Game>((games?.games ?? []).map(g => [g.key, g]))
  const ticketUrl = settings?.ticket_panel_url ?? null

  return (
    <main className="relative pt-10 pb-24">
      <div className="pointer-events-none absolute inset-0 overflow-x-clip" aria-hidden="true">
        <div className="halo" style={{ left: "6%", top: 200, width: 640, height: 460, background: "rgb(255 138 61 / 0.08)" }} />
      </div>
      <div className="relative mx-auto max-w-[1440px] px-6 min-[1100px]:px-20">
        <SectionHeading
          as="h1"
          title="L’état-major"
          sub="Les gradés qui font tourner la caserne. Besoin d’eux ? Ouvre un ticket avec Hermes, ils répondent sans que leurs MP explosent."
        />

        {/* Sans salon de tickets réglé, un bouton mort sur chaque carte n'aiderait personne : on explique. */}
        {members.length > 0 && !ticketUrl && (
          <Note>
            Pour joindre le staff, tape <code className="font-mono text-cyan">/newticket</code> sur le Discord : Hermes
            ouvre un ticket privé avec l’état-major.
          </Note>
        )}

        {members.length === 0 ? (
          <Note status>
            {staff && !staff.stale
              ? "L’état-major n’a encore aucun gradé à présenter."
              : "L’état-major est injoignable pour l’instant. Reviens dans un moment, la relève est assurée."}
          </Note>
        ) : (
          <>
            {staff?.stale && (
              <p className="mt-6 mb-0 text-sm text-muted" role="status">
                Hermes ne répond pas : voici le dernier état-major connu, grades et niveaux peuvent manquer.
              </p>
            )}
            <div className="mt-7 grid grid-cols-3 gap-5 max-[1000px]:grid-cols-2 max-[600px]:grid-cols-[minmax(0,1fr)]">
              {members.map(m => (
                <StaffCard key={m.id} member={m} games={gamesByKey} ticketUrl={ticketUrl} />
              ))}
            </div>
          </>
        )}
      </div>
    </main>
  )
}
