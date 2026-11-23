"use client"

import { useMemo, useState } from "react"
import { Chip } from "@/components/ui/chip"
import type { AchievementWithStatus } from "@/lib/api/types"
import { cn } from "@/lib/cn"
import { formatDate } from "@/lib/format"
import { achievementCategory } from "@/lib/members"
import type { RarityById } from "@/lib/rarity"

const PER_PAGE = 12
const ALL = "Tous"

type Props = {
  achievements: AchievementWithStatus[]
  /** Rareté réelle (`/achievements`) ; un succès absent n'affiche pas d'étiquette de rareté. */
  rarities?: RarityById
}

/** Succès d'un membre : filtre par catégorie, pagination, succès manquants grisés. */
export function AchievementsPanel({ achievements, rarities = {} }: Props) {
  const [category, setCategory] = useState(ALL)
  const [page, setPage] = useState(1)

  const categories = useMemo(
    () => [ALL, ...[...new Set(achievements.map(a => achievementCategory(a.condition_type)))].sort()],
    [achievements],
  )
  const filtered = useMemo(
    () => (category === ALL ? achievements : achievements.filter(a => achievementCategory(a.condition_type) === category)),
    [achievements, category],
  )
  const totalPages = Math.max(1, Math.ceil(filtered.length / PER_PAGE))
  const current = Math.min(page, totalPages)
  const items = filtered.slice((current - 1) * PER_PAGE, current * PER_PAGE)
  const unlocked = achievements.filter(a => a.unlocked).length

  return (
    <div>
      <p className="mt-0 mb-4 text-sm text-muted">
        {unlocked} sur {achievements.length} débloqués
      </p>

      <div className="mb-6 flex flex-wrap gap-2" role="group" aria-label="Catégories de succès">
        {categories.map(c => (
          <button
            key={c}
            type="button"
            aria-pressed={c === category}
            onClick={() => {
              setCategory(c)
              setPage(1)
            }}
            className={cn(
              "rounded-full border px-3 py-1.5 text-sm font-medium transition-colors",
              c === category
                ? "border-violet bg-violet/15 text-fg"
                : "border-line text-muted hover:border-violet/40 hover:text-fg",
            )}
          >
            {c}
          </button>
        ))}
      </div>

      {items.length === 0 ? (
        <p className="m-0 text-muted">Aucun succès dans cette catégorie.</p>
      ) : (
        <ul className="m-0 mb-6 grid list-none grid-cols-2 gap-3 p-0 max-[700px]:grid-cols-[minmax(0,1fr)]">
          {items.map(a => {
            const rarity = rarities[a.id]
            return (
              <li
                key={a.id}
                data-unlocked={a.unlocked}
                className={cn(
                  "flex items-start gap-3 rounded-2xl border border-line bg-[rgb(19_22_42/0.9)] p-4",
                  !a.unlocked && "opacity-50 grayscale",
                )}
              >
                <span className="relative shrink-0 text-3xl" aria-hidden="true">
                  {a.icon}
                  {!a.unlocked && <span className="absolute -right-1 -bottom-1 text-sm">🔒</span>}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="m-0 font-semibold">
                    {a.name}
                    {!a.unlocked && <span className="sr-only"> (non débloqué)</span>}
                  </p>
                  <p className="mt-0.5 mb-0 text-sm text-muted">{a.description}</p>
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    {rarity && <Chip color={rarity.color}>{rarity.label}</Chip>}
                    <span className="text-xs font-medium text-cyan">+{a.points} pts</span>
                    {a.unlocked && a.unlocked_at && (
                      <span className="text-xs text-muted">{formatDate(a.unlocked_at)}</span>
                    )}
                  </div>
                </div>
              </li>
            )
          })}
        </ul>
      )}

      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-3">
          <button
            type="button"
            aria-label="Page précédente"
            disabled={current === 1}
            onClick={() => setPage(current - 1)}
            className="rounded-lg border border-line px-3 py-1.5 text-sm disabled:opacity-40"
          >
            ←
          </button>
          <span className="text-sm text-muted tabular-nums">
            {current} / {totalPages}
          </span>
          <button
            type="button"
            aria-label="Page suivante"
            disabled={current === totalPages}
            onClick={() => setPage(current + 1)}
            className="rounded-lg border border-line px-3 py-1.5 text-sm disabled:opacity-40"
          >
            →
          </button>
        </div>
      )}
    </div>
  )
}
