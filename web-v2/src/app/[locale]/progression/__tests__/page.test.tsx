import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const cookieJar = new Map<string, string>()
vi.mock("next/headers", () => ({
  cookies: async () => ({ get: (name: string) => (cookieJar.has(name) ? { value: cookieJar.get(name) } : undefined) }),
}))

const api = vi.hoisted(() => ({
  getGrades: vi.fn(),
  getSessionUser: vi.fn(),
  getUserAchievementsAll: vi.fn(),
  getWeeklyQuests: vi.fn(),
  leaderboardLevels: vi.fn(),
}))
vi.mock("@/lib/api/server", () => api)

import ProgressionPage from "@/app/[locale]/progression/page"

const GRADE = { name: "Sergent Merguez", slug: "sergent-merguez", color: "#9B6BFF" }

beforeEach(() => {
  api.getGrades.mockResolvedValue([
    { ...GRADE, level_min: 10 },
    { name: "Recrue Cocktail", slug: "recrue-cocktail", color: "#9A97B8", level_min: 1 },
  ])
  api.leaderboardLevels.mockResolvedValue({
    leaderboard: [
      { user_id: "7", username: "Kéfir", discord_avatar: null, current_level: 19, total_xp: 36100, global_rank: 1, grade: GRADE },
    ],
    total: 1,
    page: 1,
    limit: 10,
  })
  api.getUserAchievementsAll.mockResolvedValue([
    { id: 1, name: "Bavard", description: "100 messages", icon: "💬", points: 25, condition_type: "messages", unlocked: false, unlocked_at: null },
  ])
  api.getSessionUser.mockResolvedValue({ user_id: "7", is_admin: false, is_redacteur: false })
  api.getWeeklyQuests.mockResolvedValue([])
})

afterEach(() => {
  cleanup()
  cookieJar.clear()
  vi.clearAllMocks()
})

describe("page /progression", () => {
  it("rend toutes les sections pour un visiteur, avec le catalogue de succès anonyme", async () => {
    render(await ProgressionPage())
    expect(screen.getByRole("heading", { level: 1, name: "Ta fiche de Général" })).toBeTruthy()
    expect(screen.getByRole("list", { name: "Échelle des grades" })).toBeTruthy()
    expect(screen.getByText("Exemple")).toBeTruthy()
    expect(screen.getByText(/Connecte-toi/)).toBeTruthy()
    expect(screen.getByText("Bavard")).toBeTruthy()
    expect(screen.getByRole("link", { name: "Kéfir" }).getAttribute("href")).toBe("/u/7")
    expect(api.getSessionUser).not.toHaveBeenCalled()
    expect(api.getWeeklyQuests).not.toHaveBeenCalled()
    expect(api.getUserAchievementsAll).toHaveBeenCalledWith("0")
    expect(api.leaderboardLevels).toHaveBeenCalledWith(1, 10)
  })

  it("lit la session (cookie __Secure-) pour les quêtes et les succès du membre", async () => {
    cookieJar.set("__Secure-better-auth.session_token", "tok.sig")
    render(await ProgressionPage())
    expect(api.getSessionUser).toHaveBeenCalledWith("tok.sig")
    expect(api.getWeeklyQuests).toHaveBeenCalledWith("tok.sig")
    expect(api.getUserAchievementsAll).toHaveBeenCalledWith("7")
    expect(screen.getByText(/Pas de quête cette semaine/)).toBeTruthy()
    expect(screen.getByText(/0 sur 1 débloqués/)).toBeTruthy()
  })

  it("reste debout quand web-api est indisponible", async () => {
    cookieJar.set("better-auth.session_token", "tok")
    api.getGrades.mockResolvedValue(null)
    api.getSessionUser.mockResolvedValue(null)
    api.leaderboardLevels.mockRejectedValue(new Error("fetch failed"))
    api.getUserAchievementsAll.mockRejectedValue(new Error("fetch failed"))
    render(await ProgressionPage())
    expect(screen.getByRole("heading", { level: 1 })).toBeTruthy()
    expect(screen.queryByRole("list", { name: "Échelle des grades" })).toBeNull()
    expect(screen.getByText("Exemple")).toBeTruthy()
    expect(screen.getByText(/Quêtes indisponibles/)).toBeTruthy()
    expect(screen.queryByText("Vitrine de succès")).toBeNull()
    expect(screen.getByText(/Classement indisponible/)).toBeTruthy()
  })
})
