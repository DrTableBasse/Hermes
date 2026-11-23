import type { Metadata } from "next"
import { QuestCard } from "@/components/account/quest-card"
import { SectionHeading } from "@/components/ui/section-heading"
import { getSessionUser, getWeeklyQuests } from "@/lib/api/server"
import { sessionToken } from "@/lib/session"

export const metadata: Metadata = {
  title: "Quêtes · SaucisseLand",
}

function Note({ children }: { children: React.ReactNode }) {
  return (
    <p className="mt-10 mb-0 rounded-2xl border border-line bg-[rgb(19_22_42/0.6)] px-6 py-5 text-muted" role="status">
      {children}
    </p>
  )
}

/** Défis hebdomadaires du membre connecté. `src/proxy.ts` renvoie déjà à l'accueil sans session. */
export default async function QuestsPage() {
  const token = await sessionToken()
  const me = token ? await getSessionUser(token) : null
  const quests = token && me ? await getWeeklyQuests(token) : null

  return (
    <main className="relative pt-10 pb-24">
      <div className="relative mx-auto max-w-[760px] px-6">
        <SectionHeading as="h1" title="Défis de la semaine" sub="Les défis se réinitialisent chaque lundi." />
        {quests === null ? (
          <Note>Tes quêtes sont injoignables pour l’instant. Hermes recompte, reviens dans un moment.</Note>
        ) : quests.length === 0 ? (
          <Note>Aucun défi actif cette semaine. Repos, soldat.</Note>
        ) : (
          <ul className="m-0 mt-10 grid list-none gap-4 p-0">
            {quests.map(q => (
              <QuestCard key={q.id} quest={q} />
            ))}
          </ul>
        )}
      </div>
    </main>
  )
}
