import type { Metadata } from "next"
import { AbsurdConsole } from "@/components/hermes/absurd-console"
import { CommandsGrid } from "@/components/hermes/commands-grid"
import { DailyReport } from "@/components/hermes/daily-report"
import { StatusBoard } from "@/components/hermes/status-board"
import { SectionHeading } from "@/components/ui/section-heading"
import { gameCommands } from "@/content/commands"
import { getGames, getHermesStatus } from "@/lib/api/server"

export const metadata: Metadata = {
  title: "Hermes · SaucisseLand",
  description: "Le tableau de bord d’Hermes, le bot de SaucisseLand : statut, rapport du jour et commandes commentées.",
}

export default async function HermesPage() {
  // `null` : web-api muette ; le tableau de bord l'annonce, console et commandes des cogs restent
  // (contenu statique) ; les commandes d'appel des jeux, lues en base, manquent alors.
  const [status, games] = await Promise.all([getHermesStatus(), getGames()])
  const now = new Date().getTime()

  return (
    <main className="relative pt-10 pb-24">
      <div className="pointer-events-none absolute inset-0 overflow-x-clip" aria-hidden="true">
        <div className="halo" style={{ left: "10%", top: 200, width: 700, height: 500, background: "rgb(77 124 255 / 0.12)" }} />
      </div>
      <div className="relative mx-auto max-w-[1440px] px-6 min-[1100px]:px-20">
        <SectionHeading
          as="h1"
          title="Hermes, notre bot maison"
          sub="Il compte l’XP, distribue les grades, ouvre les tickets et rappelle le bump. Il ne dort jamais. Il ne s’en plaint pas. Enfin, pas trop."
        />

        <div
          className="mt-12 grid gap-[18px] rounded-[26px] border border-blue/30 bg-[linear-gradient(160deg,rgb(77_124_255/0.14),rgb(19_22_42/0.92)_40%)] p-6 shadow-[0_0_60px_rgb(77_124_255/0.15),0_30px_60px_rgb(0_0_0/0.45)] max-[560px]:p-4"
          data-testid="hermes-dashboard"
        >
          <StatusBoard status={status} />
          <div className="grid grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)] gap-3.5 max-[1000px]:grid-cols-[minmax(0,1fr)]">
            <DailyReport status={status} />
            {/* Graine à la minute : l'ordre change d'une visite à l'autre, identique entre serveur et client. */}
            <AbsurdConsole seed={Math.floor(now / 60_000)} startedAt={now} />
          </div>
        </div>

        <section className="mt-20" aria-labelledby="commandes-title">
          <SectionHeading
            id="commandes-title"
            title="Ses commandes, commentées par lui-même"
            sub="Toutes les commandes slash d’Hermes, à taper dans Discord. Certaines sont réservées au staff : Hermes vérifie les galons."
          />
          <CommandsGrid gameCommands={gameCommands(games?.games ?? [])} />
        </section>
      </div>
    </main>
  )
}
