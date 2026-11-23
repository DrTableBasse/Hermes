import { Events } from "@/components/home/events"
import { FinalCta } from "@/components/home/final-cta"
import { GalleryPreview } from "@/components/home/gallery-preview"
import { GamesStrip } from "@/components/home/games-strip"
import { GradesTimeline } from "@/components/home/grades-timeline"
import { Hero } from "@/components/home/hero"
import { LiveBarracks } from "@/components/home/live-barracks"
import { RangDemo } from "@/components/home/rang-demo"
import {
  getEvents,
  getGalleryHighlights,
  getGames,
  getGrades,
  getHermesStatus,
  getLive,
  getLiveFeed,
  getPublicSettings,
} from "@/lib/api/server"

export default async function HomePage() {
  // Chaque section tolère sa source absente (`null`) : une API muette ne casse pas l'accueil.
  const [live, feed, grades, games, settings, events, hermes, moments] = await Promise.all([
    getLive(),
    getLiveFeed(),
    getGrades(),
    getGames(),
    getPublicSettings(),
    getEvents(),
    getHermesStatus(),
    getGalleryHighlights(),
  ])
  const inviteUrl = settings?.invite_url ?? null
  const gameList = games?.games ?? null
  const now = new Date()

  return (
    <main>
      <Hero live={live} grades={grades} gamesCount={gameList?.length ?? null} inviteUrl={inviteUrl} />
      <LiveBarracks live={live} feed={feed} now={now} />
      <GamesStrip games={gameList} now={now} inviteUrl={inviteUrl} />
      <Events data={events} />
      <GradesTimeline grades={grades} />
      <RangDemo status={hermes} grades={grades} />
      <GalleryPreview data={moments} />
      <FinalCta live={live} inviteUrl={inviteUrl} />
    </main>
  )
}
