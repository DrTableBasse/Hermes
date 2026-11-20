import { GamesStrip } from "@/components/home/games-strip"
import { Hero } from "@/components/home/hero"
import { LiveBarracks } from "@/components/home/live-barracks"
import { getGames, getGrades, getLive, getLiveFeed, getPublicSettings } from "@/lib/api/server"

export default async function HomePage() {
  // Chaque section tolère sa source absente (`null`) : une API muette ne casse pas l'accueil.
  const [live, feed, grades, games, settings] = await Promise.all([
    getLive(),
    getLiveFeed(),
    getGrades(),
    getGames(),
    getPublicSettings(),
  ])
  const inviteUrl = settings?.invite_url ?? null
  const gameList = games?.games ?? null
  const now = new Date()

  return (
    <main>
      <Hero live={live} grades={grades} gamesCount={gameList?.length ?? null} inviteUrl={inviteUrl} />
      <LiveBarracks live={live} feed={feed} now={now} />
      <GamesStrip games={gameList} now={now} inviteUrl={inviteUrl} />
    </main>
  )
}
