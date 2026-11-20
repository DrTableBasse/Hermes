import Link from "next/link"
import { Avatar } from "@/components/ui/avatar"
import { GradeBadge } from "@/components/ui/grade-badge"
import type { LevelEntry } from "@/lib/api/types"
import { cn } from "@/lib/cn"
import { formatNumber } from "@/lib/format"

/** Classement réel par niveau (`/leaderboard/levels`) ; `null` : API indisponible. */
export function LeaderboardTable({ entries }: { entries: LevelEntry[] | null }) {
  return (
    <section
      aria-labelledby="leaderboard-title"
      className="mt-6 overflow-hidden rounded-[20px] border border-line bg-[rgb(19_22_42/0.85)]"
    >
      <div className="border-b border-line px-6 py-4.5">
        <h2 id="leaderboard-title" className="m-0 font-display text-lg font-bold">
          Classement par niveau
          <span className="ml-2 font-sans text-sm font-medium text-muted">classement réel, mis à jour par Hermes</span>
        </h2>
      </div>
      {entries === null ? (
        <p className="m-0 px-6 py-5 text-sm text-muted">Classement indisponible pour l’instant. Hermes recompte.</p>
      ) : entries.length === 0 ? (
        <p className="m-0 px-6 py-5 text-sm text-muted">Personne au classement pour l’instant.</p>
      ) : (
        <table className="w-full border-collapse text-sm">
          <thead className="sr-only">
            <tr>
              <th scope="col">Rang</th>
              <th scope="col">Membre</th>
              <th scope="col">Grade</th>
              <th scope="col">Niveau</th>
              <th scope="col">XP</th>
            </tr>
          </thead>
          <tbody>
            {entries.map(e => (
              <tr key={e.user_id} className="border-b border-white/5 last:border-b-0">
                <td
                  className={cn(
                    "w-14 py-3.5 pl-6 font-display text-xl font-extrabold tabular-nums",
                    e.global_rank === 1 ? "text-orange" : "text-muted",
                  )}
                >
                  {e.global_rank}
                </td>
                <td className="max-w-0 py-3.5 pr-4">
                  <span className="flex min-w-0 items-center gap-3 font-semibold">
                    <Avatar name={e.username} src={e.discord_avatar} />
                    <Link
                      href={`/u/${encodeURIComponent(e.user_id)}`}
                      className="truncate hover:text-cyan"
                    >
                      {e.username}
                    </Link>
                  </span>
                </td>
                <td className="py-3.5 pr-4 max-[760px]:hidden">
                  <GradeBadge grade={e.grade} />
                </td>
                <td className="py-3.5 pr-4 font-semibold whitespace-nowrap tabular-nums max-[760px]:hidden">
                  niv. {formatNumber(e.current_level)}
                </td>
                <td className="py-3.5 pr-6 text-right font-semibold whitespace-nowrap tabular-nums">
                  {formatNumber(e.total_xp)} XP
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}
