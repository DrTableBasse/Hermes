import { describe, expect, it } from "vitest"
import type { Game } from "@/lib/api/types"
import { gameOfTheWeek } from "@/lib/games"

const game = (key: string): Game => ({
  key,
  name: key,
  color: "#9B6BFF",
  image: null,
  players: null,
  forum_url: null,
})

const GAMES = ["war-dogs", "dbd", "lol", "warframe", "overwatch", "fortnite", "minecraft"].map(game)
const WEEK = 7 * 86_400_000

describe("gameOfTheWeek", () => {
  it("renvoie le même jeu du lundi au dimanche d'une même semaine ISO", () => {
    // Semaine ISO 47 de 2026 : lundi 16/11 → dimanche 22/11.
    const monday = gameOfTheWeek(GAMES, new Date("2026-11-16T00:00:00Z"))
    expect(gameOfTheWeek(GAMES, new Date("2026-11-19T12:00:00Z"))).toBe(monday)
    expect(gameOfTheWeek(GAMES, new Date("2026-11-22T23:59:59Z"))).toBe(monday)
    // Le lundi suivant change de semaine.
    expect(gameOfTheWeek(GAMES, new Date("2026-11-23T00:00:00Z"))).not.toBe(monday)
  })

  it("parcourt les N jeux sur N semaines consécutives, y compris à cheval sur deux années", () => {
    // Départ fin décembre : la rotation ne doit pas sauter ni répéter au passage de l'an.
    const start = new Date("2026-12-14T10:00:00Z").getTime()
    const seen = Array.from({ length: GAMES.length }, (_, i) => gameOfTheWeek(GAMES, new Date(start + i * WEEK)).key)
    expect(new Set(seen).size).toBe(GAMES.length)
    // La semaine N+1 reprend le premier jeu du cycle.
    expect(gameOfTheWeek(GAMES, new Date(start + GAMES.length * WEEK)).key).toBe(seen[0])
  })

  it("est déterministe", () => {
    const date = new Date("2026-11-20T08:00:00Z")
    const keys = Array.from({ length: 3 }, () => gameOfTheWeek(GAMES.map(g => ({ ...g })), date).key)
    expect(new Set(keys).size).toBe(1)
  })

  it("refuse une liste vide", () => {
    expect(() => gameOfTheWeek([], new Date())).toThrow()
  })
})
