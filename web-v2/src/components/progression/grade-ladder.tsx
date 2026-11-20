import type { CSSProperties } from "react"
import type { Grade } from "@/lib/api/types"
import { formatNumber, xpForLevel } from "@/lib/format"

function levelRange(grade: Grade, next: Grade | undefined): string {
  if (!next) return `niveau ${formatNumber(grade.level_min)} et plus`
  const last = next.level_min - 1
  if (last <= grade.level_min) return `niveau ${formatNumber(grade.level_min)}`
  return `niveaux ${formatNumber(grade.level_min)} à ${formatNumber(last)}`
}

/**
 * Échelle des grades (table `grades`) : un barreau par grade, de plus en plus haut, avec la plage de
 * niveaux et l'XP totale requise (`xpForLevel`). Liste null ou vide → rien.
 */
export function GradeLadder({ grades }: { grades: Grade[] | null }) {
  if (!grades || grades.length === 0) return null
  const sorted = [...grades].sort((a, b) => a.level_min - b.level_min)

  return (
    <ol
      className="m-0 grid list-none grid-cols-[repeat(auto-fit,minmax(150px,1fr))] items-end gap-px border-b border-line bg-line p-0"
      aria-label="Échelle des grades"
    >
      {sorted.map((g, i) => (
        <li
          key={g.slug}
          data-grade={g.slug}
          className="grid h-full content-end gap-1 bg-[rgb(19_22_42)] px-4 pt-4 pb-3.5"
          style={{ "--c": g.color } as CSSProperties}
        >
          {/* Barreau : sa hauteur croît avec le rang, la couleur est celle du grade. */}
          <span
            className="mb-2 block w-8 rounded-t-md bg-[color-mix(in_srgb,var(--c)_55%,transparent)] shadow-[0_0_14px_color-mix(in_srgb,var(--c)_35%,transparent)]"
            style={{ height: 8 + i * 8 }}
            aria-hidden="true"
          />
          <b className="font-display text-[15px] text-[color-mix(in_oklab,var(--c)_60%,white)]">{g.name}</b>
          <span className="text-xs text-muted">{levelRange(g, sorted[i + 1])}</span>
          <span className="text-xs font-semibold tabular-nums">
            {formatNumber(xpForLevel(g.level_min))} XP
            <span className="font-normal text-muted"> au total</span>
          </span>
        </li>
      ))}
    </ol>
  )
}
