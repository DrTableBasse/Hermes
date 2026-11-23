import { describe, expect, it } from "vitest"
import { HERMES_LOGS, pickLogLines } from "@/content/hermes-logs"

describe("journal absurde d'Hermes", () => {
  it("compte au moins 25 lignes distinctes, dont les deux imposées", () => {
    expect(HERMES_LOGS.length).toBeGreaterThanOrEqual(25)
    const texts = HERMES_LOGS.map(l => l.text)
    expect(new Set(texts).size).toBe(texts.length)
    expect(texts.some(t => t.startsWith("Fait griller une chipolata sans la cramer"))).toBe(true)
    expect(texts.some(t => t.startsWith("Décapsule une bière sous 40 °C"))).toBe(true)
  })

  it("pickLogLines renvoie n lignes distinctes", () => {
    const lines = pickLogLines(42, 12)
    expect(lines).toHaveLength(12)
    expect(new Set(lines.map(l => l.text)).size).toBe(12)
    for (const line of lines) expect(HERMES_LOGS).toContain(line)
  })

  it("pickLogLines rend la même suite pour la même graine", () => {
    expect(pickLogLines(7, 10)).toEqual(pickLogLines(7, 10))
    expect(pickLogLines(7, 10)).not.toEqual(pickLogLines(8, 10))
  })

  it("pickLogLines plafonne n à la taille du journal", () => {
    const all = pickLogLines(3, HERMES_LOGS.length + 10)
    expect(all).toHaveLength(HERMES_LOGS.length)
    expect(new Set(all).size).toBe(HERMES_LOGS.length)
    expect(pickLogLines(3, 0)).toEqual([])
  })
})
