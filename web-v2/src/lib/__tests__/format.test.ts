import { describe, expect, it } from "vitest"
import {
  formatCountdown,
  formatNumber,
  formatSince,
  xpForLevel,
  xpProgress,
} from "@/lib/format"

describe("formatCountdown", () => {
  const now = new Date("2026-11-20T18:00:00Z")

  it("découpe l'écart en jours, heures, minutes et secondes", () => {
    const target = new Date(now.getTime() + ((2 * 24 + 3) * 3600 + 4 * 60 + 5) * 1000)
    expect(formatCountdown(target, now)).toEqual({
      days: 2, hours: 3, minutes: 4, seconds: 5, past: false,
    })
  })

  it("signale une date passée et ne renvoie jamais de valeurs négatives", () => {
    const target = new Date(now.getTime() - 90_000)
    expect(formatCountdown(target, now)).toEqual({
      days: 0, hours: 0, minutes: 0, seconds: 0, past: true,
    })
  })

  it("considère l'instant exact comme passé", () => {
    expect(formatCountdown(now, now).past).toBe(true)
  })
})

describe("formatNumber", () => {
  it("sépare les milliers par une espace insécable, à la française", () => {
    // Intl fr-FR utilise l'espace fine insécable (U+202F).
    expect(formatNumber(1234)).toBe("1 234")
    expect(formatNumber(1234)).not.toContain(" ")
  })

  it("laisse les petits nombres tels quels", () => {
    expect(formatNumber(37)).toBe("37")
  })
})

describe("formatSince", () => {
  it("donne le jour et le mois en heure de Paris", () => {
    expect(formatSince("2026-11-20T10:00:00Z")).toBe("depuis le 20/11")
    // 23 h 30 UTC le 20 = 0 h 30 le 21 à Paris.
    expect(formatSince("2026-11-20T23:30:00Z")).toBe("depuis le 21/11")
  })
})

describe("xpForLevel", () => {
  it("suit la courbe N² × 100", () => {
    expect(xpForLevel(1)).toBe(100)
    expect(xpForLevel(3)).toBe(900)
    expect(xpForLevel(45)).toBe(202_500)
  })
})

describe("xpProgress", () => {
  it("place un membre sans XP au niveau 1, barre vide", () => {
    const p = xpProgress(0)
    expect(p.level).toBe(1)
    expect(p.ratio).toBe(0)
  })

  it("donne un palier exact au début de sa barre", () => {
    expect(xpProgress(900)).toEqual({ level: 3, floor: 900, next: 1600, ratio: 0 })
  })

  it("calcule la part parcourue vers le niveau suivant", () => {
    const p = xpProgress(1250)
    expect(p.level).toBe(3)
    expect(p.ratio).toBeCloseTo(0.5)
  })

  it("reste au niveau inférieur juste sous un palier", () => {
    expect(xpProgress(1599).level).toBe(3)
    expect(xpProgress(1600).level).toBe(4)
  })

  it("traite une valeur négative ou invalide comme zéro", () => {
    expect(xpProgress(-50)).toEqual(xpProgress(0))
    expect(xpProgress(Number.NaN)).toEqual(xpProgress(0))
  })
})
