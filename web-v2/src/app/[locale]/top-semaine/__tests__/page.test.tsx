import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const api = vi.hoisted(() => ({ leaderboardXpWeekly: vi.fn(), getGrades: vi.fn() }))
vi.mock("@/lib/api/server", () => api)

import TopWeeklyPage from "@/app/[locale]/top-semaine/page"

beforeEach(() => {
  api.leaderboardXpWeekly.mockResolvedValue([
    { user_id: "7", username: "Kéfir", discord_avatar: null, total_xp: 36100, weekly_xp: 1200, current_level: 19 },
    { user_id: "8", username: "Zéro", discord_avatar: null, total_xp: 100, weekly_xp: 50, current_level: 1 },
  ])
  api.getGrades.mockResolvedValue([
    { name: "Recrue", slug: "recrue", color: "#9A97B8", level_min: 1 },
    { name: "Lieutenant", slug: "lieutenant", color: "#4D7CFF", level_min: 15 },
  ])
})
afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe("page /top-semaine", () => {
  it("XP de la semaine, grade déduit du niveau, lien vers le profil", async () => {
    render(await TopWeeklyPage())
    expect(api.leaderboardXpWeekly).toHaveBeenCalledWith(20)
    expect(screen.getByRole("link", { name: "Kéfir" }).getAttribute("href")).toBe("/u/7")
    expect(screen.getByText(/\+1.200 XP/)).toBeTruthy()
    expect(screen.getByText("Lieutenant")).toBeTruthy()
    expect(screen.getByText("Recrue")).toBeTruthy()
  })

  it("table des grades absente : niveau seul, rien d'inventé", async () => {
    api.getGrades.mockResolvedValue(null)
    render(await TopWeeklyPage())
    expect(screen.getByText("Niveau 19")).toBeTruthy()
    expect(screen.queryByText("Lieutenant")).toBeNull()
  })

  it("aucune activité", async () => {
    api.leaderboardXpWeekly.mockResolvedValue([])
    render(await TopWeeklyPage())
    expect(screen.getByRole("status").textContent).toMatch(/Aucune activité/)
  })

  it("API indisponible : message distinct de « aucune activité »", async () => {
    api.leaderboardXpWeekly.mockRejectedValue(new Error("fetch failed"))
    render(await TopWeeklyPage())
    expect(screen.getByRole("status").textContent).toMatch(/indisponible/)
  })
})
