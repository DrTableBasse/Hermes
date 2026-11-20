import { gradeForLevel } from "@/components/home/hero"
import { Avatar } from "@/components/ui/avatar"
import { Chip } from "@/components/ui/chip"
import { GradeBadge } from "@/components/ui/grade-badge"
import { XpBar } from "@/components/ui/xp-bar"
import type { Grade } from "@/lib/api/types"
import { formatNumber, xpProgress } from "@/lib/format"

// Fiche inventée (pastille « Exemple ») : un membre régulier après trois semaines.
// 21 300 XP → niveau 14 (19 600 XP), niveau 15 à 22 500 XP.
const DEMO_XP = 21_300
const DEMO_STATS: Array<[string, string]> = [
  ["9 jours", "de série"],
  [formatNumber(1284), "messages"],
  ["46 h", "en vocal"],
]

function nextGradeAfter(grades: Grade[] | null, level: number): Grade | null {
  return grades?.filter(g => g.level_min > level).sort((a, b) => a.level_min - b.level_min)[0] ?? null
}

/** Fiche de personnage d'exemple « toi, dans 3 semaines » ; grade réel lu dans `grades` s'il est connu. */
export function CharacterSheet({ grades }: { grades: Grade[] | null }) {
  const progress = xpProgress(DEMO_XP)
  const grade = gradeForLevel(grades, progress.level)
  const next = nextGradeAfter(grades, progress.level)
  const remaining = progress.next - DEMO_XP

  return (
    <div className="grid content-start gap-4" data-testid="character-sheet">
      <div className="flex flex-wrap items-center gap-2">
        <Chip example>Exemple</Chip>
        <span className="text-xs font-semibold text-muted">Toi, dans 3 semaines</span>
      </div>
      <div className="flex items-center gap-4">
        <Avatar name="Toi" color="#8E4FA8" size={76} ring={grade?.color ?? "var(--color-violet)"} />
        <div className="grid gap-1.5">
          <b className="font-display text-2xl">Toi</b>
          {grade && <GradeBadge grade={grade} />}
        </div>
      </div>
      <p className="m-0 font-display text-[44px] leading-none font-extrabold">
        Niveau {progress.level}
        <small className="ml-1.5 font-sans text-sm font-medium text-muted">{formatNumber(DEMO_XP)} XP</small>
      </p>
      <XpBar
        ratio={progress.ratio}
        height={12}
        sausage
        label={`Progression d’exemple vers le niveau ${progress.level + 1}`}
      />
      <small className="text-[13px] text-muted">
        {formatNumber(remaining)} XP avant le niveau {progress.level + 1}.
        {next && ` ${next.name} au niveau ${formatNumber(next.level_min)}.`}
      </small>
      <dl className="m-0 grid grid-cols-3 gap-2.5">
        {DEMO_STATS.map(([value, label]) => (
          <div key={label} className="flex flex-col-reverse rounded-xl border border-line bg-[rgb(12_14_26/0.55)] px-3 py-2.5">
            <dt className="text-xs text-muted">{label}</dt>
            <dd className="m-0 font-display text-xl font-bold tabular-nums">{value}</dd>
          </div>
        ))}
      </dl>
    </div>
  )
}
