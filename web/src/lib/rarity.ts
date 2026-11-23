/**
 * Rareté réelle d'un succès : part des membres actifs qui l'ont débloqué (catalogue `/achievements`).
 * Seule définition de la rareté sur le site (`/progression`, `/u/[id]`, `/profil`).
 */
import type { AchievementCatalog } from "@/lib/api/types"

export type Rarity = { slug: string; label: string; color: string }

// Rareté réelle : part des membres actifs qui ont débloqué le succès (`/achievements`).
export const RARITIES: Array<Rarity & { below: number }> = [
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

/** Rareté par identifiant de succès (objet simple : transmis tel quel à un composant client). */
export type RarityById = Record<number, Rarity>

/** Rareté de chaque succès du catalogue ; vide sans catalogue exploitable. */
export function raritiesById(catalog: AchievementCatalog | null): RarityById {
  const out: RarityById = {}
  if (!catalog || catalog.members_total <= 0) return out
  for (const a of catalog.achievements) {
    out[a.id] = rarityOf(Math.min(1, a.unlocked_count / catalog.members_total))
  }
  return out
}
