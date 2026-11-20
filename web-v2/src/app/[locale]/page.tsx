import { GamesStrip } from "@/components/home/games-strip"
import { Hero } from "@/components/home/hero"
import { LiveBarracks } from "@/components/home/live-barracks"
import { Footer } from "@/components/layout/footer"
import { Navbar } from "@/components/layout/navbar"
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

  // Navbar et pied de page montés ici tant que le layout ne les porte pas (/_kit monte les siens en démo).
  return (
    <>
      <Navbar inviteUrl={inviteUrl} />
      <main>
        <Hero live={live} grades={grades} gamesCount={gameList?.length ?? null} inviteUrl={inviteUrl} />
        <LiveBarracks live={live} feed={feed} now={now} />
        <GamesStrip games={gameList} now={now} inviteUrl={inviteUrl} />
      </main>
      <Footer ticketPanelUrl={settings?.ticket_panel_url ?? null} />
    </>
  )
}
