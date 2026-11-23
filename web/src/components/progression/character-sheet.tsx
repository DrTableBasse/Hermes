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

/** Membre connecté : ses vrais chiffres remplacent la fiche d'exemple. */
export interface SheetMember {
  name: string
  avatar: string | null
  xp: number
  streakDays: number
  messages: number
  voiceHours: number
}

/**
 * Fiche de personnage. Visiteur : exemple « toi, dans 3 semaines ». Membre connecté : sa propre fiche.
 * Le grade est lu dans `grades` s'il est connu.
 */
export function CharacterSheet({ grades, member = null }: { grades: Grade[] | null; member?: SheetMember | null }) {
  const xp = member ? member.xp : DEMO_XP
  const progress = xpProgress(xp)
  const grade = gradeForLevel(grades, progress.level)
  const next = nextGradeAfter(grades, progress.level)
  const remaining = progress.next - xp
  const name = member?.name ?? "Toi"
  const stats: Array<[string, string]> = member
    ? [
        [`${formatNumber(member.streakDays)} jour${member.streakDays > 1 ? "s" : ""}`, "de série"],
        [formatNumber(member.messages), "messages"],
        [`${formatNumber(Math.floor(member.voiceHours))} h`, "en vocal"],
      ]
    : DEMO_STATS

  return (
    <div className="grid content-start gap-4" data-testid="character-sheet">
      <div className="flex flex-wrap items-center gap-2">
        {member ? (
          <span className="text-xs font-semibold text-cyan">Ta fiche, en direct</span>
        ) : (
          <>
            <Chip example>Exemple</Chip>
            <span className="text-xs font-semibold text-muted">Toi, dans 3 semaines</span>
          </>
        )}
      </div>
      <div className="flex items-center gap-4">
        <Avatar
          name={name}
          src={member?.avatar ?? null}
          color={member ? undefined : "#8E4FA8"}
          size={76}
          ring={grade?.color ?? "var(--color-violet)"}
        />
        <div className="grid gap-1.5">
          <b className="font-display text-2xl">{name}</b>
          {grade && <GradeBadge grade={grade} />}
        </div>
      </div>
      <p className="m-0 font-display text-[44px] leading-none font-extrabold">
        Niveau {progress.level}
        <small className="ml-1.5 font-sans text-sm font-medium text-muted">{formatNumber(xp)} XP</small>
      </p>
      <XpBar
        ratio={progress.ratio}
        height={12}
        sausage
        label={`${member ? "Ta progression" : "Progression d’exemple"} vers le niveau ${progress.level + 1}`}
      />
      <small className="text-[13px] text-muted">
        {formatNumber(remaining)} XP avant le niveau {progress.level + 1}.
        {next && ` ${next.name} au niveau ${formatNumber(next.level_min)}.`}
      </small>
      <dl className="m-0 grid grid-cols-3 gap-2.5">
        {stats.map(([value, label]) => (
          <div key={label} className="flex flex-col-reverse rounded-xl border border-line bg-[rgb(12_14_26/0.55)] px-3 py-2.5">
            <dt className="text-xs text-muted">{label}</dt>
            <dd className="m-0 font-display text-xl font-bold tabular-nums">{value}</dd>
          </div>
        ))}
      </dl>
    </div>
  )
}
