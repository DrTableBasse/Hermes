import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const notFound = vi.hoisted(() =>
  vi.fn(() => {
    throw new Error("NEXT_NOT_FOUND")
  }),
)
vi.mock("next/navigation", () => ({ notFound }))

const api = vi.hoisted(() => ({
  getUserPublicStats: vi.fn(),
  getUserActivity: vi.fn(),
  getUserAchievementsAll: vi.fn(),
  getAchievementCatalog: vi.fn(),
}))
vi.mock("@/lib/api/server", () => api)

import PublicProfilePage from "@/app/[locale]/u/[userId]/page"

const GRADE = { name: "Sergent Merguez", slug: "sergent", color: "#FF8A3D" }
const ACH = { id: 1, name: "Bavard", description: "100 messages", icon: "💬", points: 100 }
const PUBLIC = {
  user_id: "123",
  username: "kefir",
  nickname: "Kéfir",
  discord_avatar: null,
  stats: {
    total_messages: 1500,
    voice_seconds: 3600,
    voice_formatted: "1h 0m",
    total_xp: 36100,
    current_level: 19,
    grade: GRADE,
    achievement_count: 1,
    current_streak: 4,
    bump_count: 2,
  },
  achievements: [{ ...ACH, unlocked_at: "2026-11-01T10:00:00Z" }],
}

const run = (userId: string) => PublicProfilePage({ params: Promise.resolve({ userId }) }).then(render)

// Rareté réelle : « Bavard » (100 pts) est débloqué par 60 % des membres → Commun, pas Légendaire.
const CATALOG = {
  members_total: 10,
  achievements: [
    { ...ACH, condition_type: "messages", unlocked_count: 6 },
    { id: 2, name: "Noctambule", description: "vocal de nuit", icon: "🌙", points: 25, condition_type: "voice_night_minutes", unlocked_count: 0 },
  ],
}

beforeEach(() => {
  api.getAchievementCatalog.mockResolvedValue(CATALOG)
  api.getUserPublicStats.mockResolvedValue(PUBLIC)
  api.getUserActivity.mockResolvedValue([{ date: "2026-11-01", count: 4 }])
  api.getUserAchievementsAll.mockResolvedValue([
    { ...ACH, condition_type: "messages", unlocked: true, unlocked_at: "2026-11-01T10:00:00Z" },
    { id: 2, name: "Noctambule", description: "vocal de nuit", icon: "🌙", points: 25, condition_type: "voice_night_minutes", unlocked: false, unlocked_at: null },
  ])
})
afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe("page /u/[userId]", () => {
  it("profil complet : nom, pseudo, grade, niveau, statistiques, activité, raretés, succès", async () => {
    await run("123")
    expect(screen.getByRole("heading", { level: 1, name: "Kéfir" })).toBeTruthy()
    expect(screen.getByText("@kefir")).toBeTruthy()
    expect(screen.getAllByText("Sergent Merguez").length).toBeGreaterThan(0)
    expect(screen.getByText("niveau 19")).toBeTruthy()
    expect(screen.getByText("1h 0m")).toBeTruthy()
    expect(screen.getByText("4 j")).toBeTruthy()
    expect(screen.getByRole("figure", { name: /Activité/ })).toBeTruthy()
    expect(screen.getByRole("heading", { name: "Raretés des succès" })).toBeTruthy()
    expect(screen.getByText("1 Commun")).toBeTruthy()
    expect(screen.queryByText("1 Légendaire")).toBeNull() // ancien palier par points (100 pts)
    expect(screen.queryByRole("heading", { name: "Réputation" })).toBeNull()
    expect(screen.getByText(/1 sur 2 débloqués/)).toBeTruthy()
    expect(api.getUserPublicStats).toHaveBeenCalledWith("123")
  })

  it("rareté réelle : même étiquette que /progression, par succès", async () => {
    await run("123")
    // Noctambule (0 %) est Légendaire, Bavard (60 %) Commun, quels que soient leurs points.
    expect(screen.getAllByText("Commun").length).toBeGreaterThan(0)
    expect(screen.getByText("Légendaire")).toBeTruthy()
  })

  it("catalogue muet : ni section de raretés, ni étiquette inventée", async () => {
    api.getAchievementCatalog.mockResolvedValue(null)
    await run("123")
    expect(screen.queryByRole("heading", { name: "Raretés des succès" })).toBeNull()
    expect(screen.queryByText(/Légendaire|Épique|Commun/)).toBeNull()
    expect(screen.getByText(/1 sur 2 débloqués/)).toBeTruthy()
  })

  it("détail des succès indisponible : retombe sur les succès débloqués du profil", async () => {
    api.getUserAchievementsAll.mockRejectedValue(new Error("500 x"))
    await run("123")
    expect(screen.getByText(/1 sur 1 débloqués/)).toBeTruthy()
  })

  it("sans activité : pas de section d'activité", async () => {
    api.getUserActivity.mockResolvedValue([])
    await run("123")
    expect(screen.queryByRole("figure")).toBeNull()
  })

  it("404 de web-api : notFound()", async () => {
    api.getUserPublicStats.mockRejectedValue(new Error("404 /users/999/public"))
    await expect(run("999")).rejects.toThrow("NEXT_NOT_FOUND")
    expect(notFound).toHaveBeenCalled()
  })

  it("identifiant qui n'est pas un snowflake : notFound() sans appel à web-api", async () => {
    await expect(run("..")).rejects.toThrow("NEXT_NOT_FOUND")
    expect(api.getUserPublicStats).not.toHaveBeenCalled()
  })

  it("API indisponible (500, réseau) : message d'indisponibilité, pas de 404", async () => {
    api.getUserPublicStats.mockRejectedValue(new Error("fetch failed"))
    await run("123")
    expect(notFound).not.toHaveBeenCalled()
    expect(screen.getByRole("status").textContent).toMatch(/injoignable/)
  })
})
