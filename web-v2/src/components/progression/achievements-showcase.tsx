import type { CSSProperties } from "react"
import { Panel } from "@/components/ui/panel"
import type { AchievementCatalog } from "@/lib/api/types"
import { cn } from "@/lib/cn"
import { formatNumber } from "@/lib/format"

export type Rarity = { slug: string; label: string; color: string }

// Rareté réelle : part des membres actifs qui ont débloqué le succès (`/achievements`).
const RARITIES: Array<Rarity & { below: number }> = [
  { slug: "legendaire", label: "Légendaire", color: "var(--color-orange)", below: 0.01 },
  { slug: "epique", label: "Épique", color: "var(--color-violet)", below: 0.05 },
  { slug: "rare", label: "Rare", color: "var(--color-blue)", below: 0.2 },
  { slug: "commun", label: "Commun", color: "var(--color-muted)", below: Infinity },
]

/** Rareté d'après la part `share` (0 à 1) des membres qui ont le succès. */
export function rarityOf(share: number): Rarity {
  const { slug, label, color } = RARITIES.find(r => share < r.below) ?? RARITIES[RARITIES.length - 1]
  return { slug, label, color }
}

const pct = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 1 })

/** « débloqué par 3 % des membres » ; une part non nulle mais minuscule ne s'affiche jamais « 0 % ». */
export function shareText(count: number, share: number): string {
  if (count === 0) return "encore jamais débloqué"
  const percent = share * 100
  if (percent < 0.1) return "débloqué par moins de 0,1 % des membres"
  return `débloqué par ${pct.format(percent < 1 ? percent : Math.round(percent))} % des membres`
}

type ShowcaseProps = {
  /** Catalogue `/achievements` ; `null` (API muette), vide ou sans membre → section masquée. */
  catalog: AchievementCatalog | null
  /** Succès du membre connecté ; `null` pour un visiteur (rien n'est grisé). */
  unlockedIds: ReadonlySet<number> | null
}

/** Vitrine des succès réels, groupés par rareté réelle, du plus rare au plus commun. */
export function AchievementsShowcase({ catalog, unlockedIds }: ShowcaseProps) {
  if (!catalog || catalog.achievements.length === 0 || catalog.members_total <= 0) return null
  const total = catalog.members_total
  const items = catalog.achievements
    .map(a => ({ ...a, share: Math.min(1, a.unlocked_count / total) }))
    .sort((a, b) => a.share - b.share || a.id - b.id)
  const groups = RARITIES.map(r => ({ rarity: r, items: items.filter(a => rarityOf(a.share).slug === r.slug) })).filter(
    g => g.items.length > 0,
  )
  const unlocked = unlockedIds ? items.filter(a => unlockedIds.has(a.id)).length : 0

  return (
    <Panel as="section" aria-labelledby="achievements-title" className="mt-6 grid gap-6 rounded-[26px] p-7 hover:border-line">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <h2 id="achievements-title" className="m-0 font-display text-2xl font-bold">
            Vitrine de succès
          </h2>
          <p className="m-0 mt-1 text-sm text-muted">
            Rareté réelle : la part des {formatNumber(total)} membres qui ont débloqué chaque succès.
          </p>
        </div>
        <span className="text-sm text-muted">
          {unlockedIds
            ? `${formatNumber(unlocked)} sur ${formatNumber(items.length)} débloqués`
            : `${formatNumber(items.length)} succès à collectionner`}
        </span>
      </div>
      {groups.map(({ rarity, items: group }) => (
        <div key={rarity.slug} data-testid="rarity-group" data-rarity={rarity.slug} className="grid gap-3">
          <h3
            className="m-0 font-display text-base font-bold text-[color-mix(in_oklab,var(--c)_60%,white)]"
            style={{ "--c": rarity.color } as CSSProperties}
          >
            {rarity.label}
            <span className="ml-2 font-sans text-sm font-medium text-muted">{formatNumber(group.length)}</span>
          </h3>
          <ul className="m-0 grid list-none grid-cols-[repeat(auto-fill,minmax(220px,1fr))] gap-3 p-0">
            {group.map(a => {
              const owned = unlockedIds?.has(a.id) ?? false
              const locked = unlockedIds !== null && !owned
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
                  {a.description && <p className="m-0 text-xs leading-snug text-muted">{a.description}</p>}
                  <small className="text-[11px] font-bold text-[color-mix(in_oklab,var(--c)_60%,white)]">
                    {shareText(a.unlocked_count, a.share)}
                    {unlockedIds && <span className="font-medium text-muted">{owned ? " · débloqué" : " · à débloquer"}</span>}
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
