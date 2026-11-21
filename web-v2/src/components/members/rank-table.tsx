import Link from "next/link"
import { Avatar } from "@/components/ui/avatar"
import { Chip } from "@/components/ui/chip"
import { GradeBadge } from "@/components/ui/grade-badge"
import { cn } from "@/lib/cn"
import type { RankRow } from "@/lib/members"
import { formatNumber } from "@/lib/format"

type RankTableProps = {
  rows: RankRow[]
  /** Membre connecté : sa ligne est marquée. Comparé en chaînes (snowflakes > 2^53). */
  meId: string | null
  /** Ligne mise en avant par `?hl=` (lien « Mon classement »). */
  highlightId?: string | null
}

/** Lignes d'un classement (rang, membre, grade et niveau s'ils existent, score). */
export function RankTable({ rows, meId, highlightId }: RankTableProps) {
  if (rows.length === 0) {
    return <p className="m-0 px-6 py-8 text-center text-muted">Aucune donnée disponible.</p>
  }
  return (
    <table className="w-full border-collapse text-sm">
      <thead className="sr-only">
        <tr>
          <th scope="col">Rang</th>
          <th scope="col">Membre</th>
          <th scope="col">Grade</th>
          <th scope="col">Score</th>
        </tr>
      </thead>
      <tbody>
        {rows.map(r => {
          const me = meId !== null && r.id === meId
          const highlighted = highlightId != null && r.id === highlightId
          return (
            <tr
              key={r.id}
              data-me={me ? "true" : undefined}
              data-highlight={highlighted ? "true" : undefined}
              className={cn(
                "border-b border-white/5 last:border-b-0",
                me && "bg-violet/8",
                highlighted && "bg-violet/15",
              )}
            >
              <td
                className={cn(
                  "w-14 py-3.5 pl-6 font-display text-xl font-extrabold tabular-nums",
                  r.rank === 1 ? "text-orange" : "text-muted",
                )}
              >
                {r.rank}
              </td>
              <td className="w-full max-w-0 py-3.5 pr-4">
                <span className="flex min-w-0 items-center gap-3 font-semibold">
                  <Avatar name={r.name} src={r.avatar} />
                  <Link href={`/u/${encodeURIComponent(r.id)}`} className="truncate hover:text-cyan">
                    {r.name}
                  </Link>
                  {me && <Chip color="var(--color-violet)">moi</Chip>}
                </span>
              </td>
              <td className="py-3.5 pr-4 max-[760px]:hidden">
                {r.grade && (
                  <span className="flex items-center gap-2 whitespace-nowrap">
                    <GradeBadge grade={r.grade} />
                    {r.level !== null && <span className="tabular-nums">niv. {formatNumber(r.level)}</span>}
                  </span>
                )}
              </td>
              <td className="py-3.5 pr-6 text-right font-semibold whitespace-nowrap tabular-nums">
                {r.score}
                {r.detail && <span className="ml-2 text-orange">{r.detail}</span>}
              </td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}
