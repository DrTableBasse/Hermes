import type { Metadata } from "next"
import { AchievementsShowcase } from "@/components/progression/achievements-showcase"
import { CharacterSheet } from "@/components/progression/character-sheet"
import { GradeLadder } from "@/components/progression/grade-ladder"
import { LeaderboardTable } from "@/components/progression/leaderboard-table"
import { WeeklyQuests } from "@/components/progression/weekly-quests"
import { SectionHeading } from "@/components/ui/section-heading"
import {
  getAchievementCatalog,
  getGrades,
  getSessionUser,
  getUserAchievementsAll,
  getWeeklyQuests,
  leaderboardLevels,
} from "@/lib/api/server"
import { sessionToken } from "@/lib/session"

export const metadata: Metadata = {
  title: "Progression · SaucisseLand",
  description: "Grades, quêtes de la semaine, succès et classement par niveau des Généraux Saucisses.",
}

export default async function ProgressionPage() {
  const token = await sessionToken()
  const me = token ? await getSessionUser(token) : null

  // Chaque bloc tolère sa source absente (`null`) : une API muette ne casse pas la page.
  const [grades, levels, quests, catalog, mine] = await Promise.all([
    getGrades(),
    leaderboardLevels(1, 10).then(
      page => page.leaderboard,
      () => null,
    ),
    token && me ? getWeeklyQuests(token) : Promise.resolve(null),
    getAchievementCatalog(),
    // Succès du membre connecté, pour griser ceux qui lui manquent ; échec → vitrine sans grisé.
    me ? getUserAchievementsAll(me.user_id).catch(() => null) : Promise.resolve(null),
  ])
  const unlockedIds = mine ? new Set(mine.filter(a => a.unlocked).map(a => a.id)) : null

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

        <AchievementsShowcase catalog={catalog} unlockedIds={unlockedIds} />
        <LeaderboardTable entries={levels} />
      </div>
    </main>
  )
}
