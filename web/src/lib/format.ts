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

const longDate = new Intl.DateTimeFormat("fr-FR", {
  day: "numeric",
  month: "long",
  year: "numeric",
  timeZone: "Europe/Paris",
})

/** « 15 novembre 2026 », date lue en heure de Paris. */
export function formatDate(iso: string): string {
  return longDate.format(new Date(iso))
}

const clock = new Intl.DateTimeFormat("fr-FR", {
  hour: "2-digit",
  minute: "2-digit",
  timeZone: "Europe/Paris",
})

/** « 21:04 », heure de Paris. */
export function formatClock(iso: string): string {
  return clock.format(new Date(iso))
}

/** « Il y a 6 min », relatif à `now` ; une date future (horloges décalées) vaut « À l'instant ». */
export function formatAgo(iso: string, now: Date): string {
  const minutes = Math.floor((now.getTime() - new Date(iso).getTime()) / 60_000)
  if (!(minutes >= 1)) return "À l'instant"
  if (minutes < 60) return `Il y a ${minutes} min`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `Il y a ${hours} h`
  return `Il y a ${Math.floor(hours / 24)} j`
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

const eventParts = new Intl.DateTimeFormat("fr-FR", {
  weekday: "long",
  day: "numeric",
  month: "long",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
  timeZone: "Europe/Paris",
})

function parisParts(iso: string): Record<string, string> {
  const parts: Record<string, string> = {}
  for (const p of eventParts.formatToParts(new Date(iso))) parts[p.type] = p.value
  return parts
}

function hourText(p: Record<string, string>): string {
  const h = Number(p.hour)
  return p.minute === "00" ? `${h} h` : `${h} h ${p.minute}`
}

/** « 20 h » ou « 20 h 05 », heure de Paris. */
export function formatEventHour(iso: string): string {
  return hourText(parisParts(iso))
}

/** « Samedi 21 novembre, 21 h », heure de Paris. */
export function formatEventWhen(iso: string): string {
  const p = parisParts(iso)
  const weekday = p.weekday.charAt(0).toUpperCase() + p.weekday.slice(1)
  return `${weekday} ${p.day} ${p.month}, ${hourText(p)}`
}

/** Pavé de date d'un event : « SAM » et « 22 », à Paris. */
export function formatEventDay(iso: string): { weekday: string; day: string } {
  const p = parisParts(iso)
  return { weekday: p.weekday.slice(0, 3).toUpperCase(), day: p.day }
}
