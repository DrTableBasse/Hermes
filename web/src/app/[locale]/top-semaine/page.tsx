import type { Metadata } from "next"
import Link from "next/link"
import { Avatar } from "@/components/ui/avatar"
import { GradeBadge } from "@/components/ui/grade-badge"
import { Panel } from "@/components/ui/panel"
import { SectionHeading } from "@/components/ui/section-heading"
import { getGrades, leaderboardXpWeekly } from "@/lib/api/server"
import { cn } from "@/lib/cn"
import { formatNumber } from "@/lib/format"
import { gradeForLevel } from "@/lib/members"

export const metadata: Metadata = {
  title: "Top de la semaine · SaucisseLand",
  description: "Les membres qui ont gagné le plus d’XP cette semaine.",
}

const MEDALS = ["🥇", "🥈", "🥉"]

export default async function TopWeeklyPage() {
  // `/xp/leaderboard` ne renvoie pas le grade : il est déduit du niveau avec la table des grades.
  const [entries, grades] = await Promise.all([leaderboardXpWeekly(20).catch(() => null), getGrades()])

  return (
    <main className="relative pt-10 pb-24">
      <div className="relative mx-auto max-w-[900px] px-6">
        <SectionHeading as="h1" title="Top de la semaine" sub="Classement par XP gagné cette semaine." />

        {entries === null ? (
          <Panel className="mt-8 text-center text-muted" role="status">
            Classement indisponible pour l’instant. Hermes recompte.
          </Panel>
        ) : entries.length === 0 ? (
          <Panel className="mt-8 text-center text-muted" role="status">
            Aucune activité cette semaine.
          </Panel>
        ) : (
          <ol className="m-0 mt-8 flex list-none flex-col gap-2 p-0">
            {entries.map((e, i) => {
              const grade = gradeForLevel(e.current_level, grades)
              return (
                <li key={e.user_id}>
                  <Panel highlight={i === 0} className={cn("flex items-center gap-4 px-5 py-4", i > 0 && i < 3 && "border-violet/25")}>
                    <span className="w-9 shrink-0 text-center font-display text-lg font-bold tabular-nums">
                      {i < 3 ? (
                        <>
                          <span aria-hidden="true">{MEDALS[i]}</span>
                          <span className="sr-only">Rang {i + 1}</span>
                        </>
                      ) : (
                        `#${i + 1}`
                      )}
                    </span>
                    <Avatar name={e.username} src={e.discord_avatar} size={40} />
                    <div className="min-w-0 flex-1">
                      <Link href={`/u/${encodeURIComponent(e.user_id)}`} className="block truncate font-semibold hover:text-cyan">
                        {e.username}
                      </Link>
                      <p className="m-0 mt-1 flex flex-wrap items-center gap-2 text-xs text-muted">
                        {grade && <GradeBadge grade={grade} />}
                        <span>Niveau {formatNumber(e.current_level)}</span>
                      </p>
                    </div>
                    <div className="shrink-0 text-right">
                      <p className="m-0 font-bold text-cyan tabular-nums">+{formatNumber(e.weekly_xp)} XP</p>
                      <p className="m-0 text-xs text-muted tabular-nums">{formatNumber(e.total_xp)} au total</p>
                    </div>
                  </Panel>
                </li>
              )
            })}
          </ol>
        )}
      </div>
    </main>
  )
}
