import type { Game } from "@/lib/api/types"

const DAY = 86_400_000
const WEEK = 7 * DAY
// Lundi 29/12/1969 (UTC) : premier jour de la semaine ISO 1 de 1970, origine du décompte.
const ISO_EPOCH_MONDAY = Date.UTC(1969, 11, 29)

/** Rang absolu de la semaine ISO (lundi → dimanche, UTC) : +1 chaque lundi, sans remise à zéro au 1er janvier. */
function isoWeekIndex(date: Date): number {
  const day = Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate())
  return Math.floor((day - ISO_EPOCH_MONDAY) / WEEK)
}

/**
 * Jeu mis en avant cette semaine : rotation déterministe dans l'ordre de la liste (ordre de l'admin),
 * un jeu par semaine ISO. Le numéro de semaine de l'année repartant à 1 en janvier, la rotation suit le
 * rang absolu de la semaine pour ne rien sauter ni répéter au passage de l'an.
 */
export function gameOfTheWeek(games: Game[], date: Date): Game {
  if (games.length === 0) throw new Error("gameOfTheWeek : liste de jeux vide")
  const n = games.length
  return games[((isoWeekIndex(date) % n) + n) % n]
}
