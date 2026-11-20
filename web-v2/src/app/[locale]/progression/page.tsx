import type { Metadata } from "next"
import { cookies } from "next/headers"
import { AchievementsShowcase } from "@/components/progression/achievements-showcase"
import { CharacterSheet } from "@/components/progression/character-sheet"
import { GradeLadder } from "@/components/progression/grade-ladder"
import { LeaderboardTable } from "@/components/progression/leaderboard-table"
import { WeeklyQuests } from "@/components/progression/weekly-quests"
import { SectionHeading } from "@/components/ui/section-heading"
import {
  getGrades,
  getSessionUser,
  getUserAchievementsAll,
  getWeeklyQuests,
  leaderboardLevels,
} from "@/lib/api/server"

export const metadata: Metadata = {
  title: "Progression · SaucisseLand",
  description: "Grades, quêtes de la semaine, succès et classement par niveau des Généraux Saucisses.",
}

// En HTTPS, BetterAuth préfixe son cookie par `__Secure-` (même liste que `src/proxy.ts`).
const SESSION_COOKIES = ["better-auth.session_token", "__Secure-better-auth.session_token"]

// Identifiant qu'aucun membre ne porte : `/users/0/achievements` rend le catalogue, tout verrouillé.
const NOBODY = "0"

async function sessionToken(): Promise<string | null> {
  const jar = await cookies()
  for (const name of SESSION_COOKIES) {
    const value = jar.get(name)?.value
    if (value) return value
  }
  return null
}

export default async function ProgressionPage() {
  const token = await sessionToken()
  const me = token ? await getSessionUser(token) : null

  // Chaque bloc tolère sa source absente (`null`) : une API muette ne casse pas la page.
  const [grades, levels, quests, achievements] = await Promise.all([
    getGrades(),
    leaderboardLevels(1, 10).then(
      page => page.leaderboard,
      () => null,
    ),
    token && me ? getWeeklyQuests(token) : Promise.resolve(null),
    getUserAchievementsAll(me?.user_id ?? NOBODY).catch(() => null),
  ])

  return (
    <main className="relative pt-10 pb-24">
      <div className="relative mx-auto max-w-[1440px] px-6 min-[1100px]:px-20">
        <SectionHeading
          as="h1"
          title="Ta fiche de Général"
          sub="Chaque message et chaque minute en vocal te rapportent de l’XP. Monte en grade, tiens ta série, collectionne les succès. Hermes tient les comptes."
        />

        <div className="mt-12 overflow-hidden rounded-[26px] border border-white/9 bg-[rgb(19_22_42/0.9)] shadow-[0_30px_60px_rgb(0_0_0/0.45)]">
          <GradeLadder grades={grades} />
          <div className="grid grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)] max-[1000px]:grid-cols-[minmax(0,1fr)]">
            <div className="border-r border-line p-7 max-[1000px]:border-r-0 max-[1000px]:border-b">
              <CharacterSheet grades={grades} />
            </div>
            <div className="p-7">
              {/* Cookie présent mais session illisible (API muette) : « indisponibles », pas « connecte-toi ». */}
              <WeeklyQuests signedIn={token !== null} quests={quests} />
            </div>
          </div>
        </div>

        <AchievementsShowcase achievements={achievements} personal={me !== null} />
        <LeaderboardTable entries={levels} />
      </div>
    </main>
  )
}
