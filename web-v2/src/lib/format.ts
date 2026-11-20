export type Countdown = {
  days: number
  hours: number
  minutes: number
  seconds: number
  past: boolean
}

/** Temps restant avant `target`, en unités entières ; tout à zéro et `past` une fois l'heure atteinte. */
export function formatCountdown(target: Date, now: Date): Countdown {
  const total = Math.floor((target.getTime() - now.getTime()) / 1000)
  if (!(total > 0)) return { days: 0, hours: 0, minutes: 0, seconds: 0, past: true }
  return {
    days: Math.floor(total / 86_400),
    hours: Math.floor((total % 86_400) / 3600),
    minutes: Math.floor((total % 3600) / 60),
    seconds: total % 60,
    past: false,
  }
}

const numberFormat = new Intl.NumberFormat("fr-FR")

/** Nombre à la française : « 1 234 » (espace fine insécable). */
export function formatNumber(n: number): string {
  return numberFormat.format(n)
}

const dayMonth = new Intl.DateTimeFormat("fr-FR", {
  day: "2-digit",
  month: "2-digit",
  timeZone: "Europe/Paris",
})

/** « depuis le 20/11 », date lue en heure de Paris. */
export function formatSince(iso: string): string {
  return `depuis le ${dayMonth.format(new Date(iso))}`
}

/** XP totale pour atteindre `level` : N² × 100. */
export function xpForLevel(level: number): number {
  return level * level * 100
}

export type XpProgress = { level: number; floor: number; next: number; ratio: number }

/** Niveau courant (`max(1, ⌊√(xp/100)⌋)`) et avancement vers le suivant, `ratio` borné à [0, 1]. */
export function xpProgress(totalXp: number): XpProgress {
  const xp = Number.isFinite(totalXp) && totalXp > 0 ? totalXp : 0
  let level = Math.max(1, Math.floor(Math.sqrt(xp / 100)))
  // La racine flottante peut tomber d'un cran à côté près des paliers.
  while (xpForLevel(level + 1) <= xp) level++
  while (level > 1 && xpForLevel(level) > xp) level--

  const floor = xpForLevel(level)
  const next = xpForLevel(level + 1)
  const ratio = Math.min(1, Math.max(0, (xp - floor) / (next - floor)))
  return { level, floor, next, ratio }
}
