import type { CSSProperties } from "react"
import { Panel } from "@/components/ui/panel"
import type { AchievementWithStatus } from "@/lib/api/types"
import { cn } from "@/lib/cn"
import { formatNumber } from "@/lib/format"

export type Rarity = { slug: string; label: string; color: string }

// La table `achievements` n'a pas de rareté : elle se déduit des points (10-15, 20-35, 40-60, 75+).
const RARITIES: Array<Rarity & { min: number }> = [
  { slug: "legendaire", label: "Légendaire", color: "var(--color-orange)", min: 75 },
  { slug: "epique", label: "Épique", color: "var(--color-violet)", min: 40 },
  { slug: "rare", label: "Rare", color: "var(--color-blue)", min: 20 },
  { slug: "commun", label: "Commun", color: "var(--color-muted)", min: -Infinity },
]

export function rarityOf(points: number): Rarity {
  const { slug, label, color } = RARITIES.find(r => points >= r.min) ?? RARITIES[RARITIES.length - 1]
  return { slug, label, color }
}

type ShowcaseProps = {
  /** Tous les succès en base ; `null` (API indisponible) ou vide → section masquée. */
  achievements: AchievementWithStatus[] | null
  /** Membre connecté : ses succès non débloqués sont grisés. */
  personal: boolean
}

/** Vitrine des succès réels, groupés par rareté, du plus rare au plus commun. */
export function AchievementsShowcase({ achievements, personal }: ShowcaseProps) {
  if (!achievements || achievements.length === 0) return null
  const unlocked = achievements.filter(a => a.unlocked).length
  const groups = RARITIES.map(r => ({
    rarity: r,
    items: achievements.filter(a => rarityOf(a.points).slug === r.slug),
  })).filter(g => g.items.length > 0)

  return (
    <Panel as="section" aria-labelledby="achievements-title" className="mt-6 grid gap-6 rounded-[26px] p-7 hover:border-line">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h2 id="achievements-title" className="m-0 font-display text-2xl font-bold">
          Vitrine de succès
        </h2>
        <span className="text-sm text-muted">
          {personal
            ? `${formatNumber(unlocked)} sur ${formatNumber(achievements.length)} débloqués`
            : `${formatNumber(achievements.length)} succès à collectionner`}
        </span>
      </div>
      {groups.map(({ rarity, items }) => (
        <div key={rarity.slug} data-testid="rarity-group" data-rarity={rarity.slug} className="grid gap-3">
          <h3
            className="m-0 font-display text-base font-bold text-[color-mix(in_oklab,var(--c)_60%,white)]"
            style={{ "--c": rarity.color } as CSSProperties}
          >
            {rarity.label}
            <span className="ml-2 font-sans text-sm font-medium text-muted">{formatNumber(items.length)}</span>
          </h3>
          <ul className="m-0 grid list-none grid-cols-[repeat(auto-fill,minmax(220px,1fr))] gap-3 p-0">
            {items.map(a => {
              const locked = personal && !a.unlocked
              return (
                <li
                  key={a.id}
                  data-locked={locked}
                  className={cn(
                    "grid content-start gap-1.5 rounded-2xl border border-[color-mix(in_srgb,var(--c)_50%,transparent)] bg-linear-160 from-[color-mix(in_srgb,var(--c)_22%,transparent)] to-[rgb(12_14_26/0.6)] p-3.5 transition-transform duration-250 motion-safe:hover:-translate-y-0.5",
                    locked && "opacity-55 grayscale",
                  )}
                  style={{ "--c": rarity.color } as CSSProperties}
                >
                  <span
                    className="grid size-10 place-items-center rounded-xl bg-[color-mix(in_srgb,var(--c)_30%,transparent)] text-xl"
                    aria-hidden="true"
                  >
                    {a.icon}
                  </span>
                  <b className="font-display text-[15px] leading-tight">{a.name}</b>
                  <p className="m-0 text-xs leading-snug text-muted">{a.description}</p>
                  <small className="text-[11px] font-bold text-[color-mix(in_oklab,var(--c)_60%,white)]">
                    {formatNumber(a.points)} points
                    {personal && <span className="font-medium text-muted">{a.unlocked ? " · débloqué" : " · à débloquer"}</span>}
                  </small>
                </li>
              )
            })}
          </ul>
        </div>
      ))}
    </Panel>
  )
}
