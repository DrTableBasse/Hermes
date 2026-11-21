import { cleanup, render, screen, within } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const cookieJar = new Map<string, string>()
vi.mock("next/headers", () => ({
  cookies: async () => ({ get: (name: string) => (cookieJar.has(name) ? { value: cookieJar.get(name) } : undefined) }),
}))
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  usePathname: () => "/classement",
  useSearchParams: () => new URLSearchParams(),
}))

const api = vi.hoisted(() => ({
  getSessionUser: vi.fn(),
  myRanks: vi.fn(),
  leaderboardVoice: vi.fn(),
  leaderboardMessages: vi.fn(),
  leaderboardAchievements: vi.fn(),
  leaderboardBumps: vi.fn(),
  leaderboardInvites: vi.fn(),
  leaderboardLevels: vi.fn(),
  leaderboardStreaks: vi.fn(),
}))
vi.mock("@/lib/api/server", () => api)

import ClassementPage from "@/app/[locale]/classement/page"

const GRADE = { name: "Sergent Merguez", slug: "sergent", color: "#FF8A3D" }
const lvl = (id: string, rank: number, name: string) => ({
  user_id: id,
  username: name,
  discord_avatar: null,
  current_level: 20 - rank,
  total_xp: 1000 * (10 - rank),
  global_rank: rank,
  grade: GRADE,
})
const LEVELS = [lvl("1", 1, "Un"), lvl("2", 2, "Deux"), lvl("3", 3, "Trois"), lvl("4", 4, "Quatre"), lvl("5", 5, "Cinq")]

const run = async (sp: Record<string, string> = {}) => render(await ClassementPage({ searchParams: Promise.resolve(sp) }))

beforeEach(() => {
  api.leaderboardLevels.mockResolvedValue({ leaderboard: LEVELS, total: 25, page: 1, limit: 10 })
  api.leaderboardVoice.mockResolvedValue({
    leaderboard: [{ user_id: "9", username: "Vocal", discord_avatar: null, total_seconds: 60, formatted: "1h 0m", global_rank: 1 }],
    total: 1,
    page: 1,
    limit: 10,
  })
  api.getSessionUser.mockResolvedValue({ user_id: "5", is_admin: false, is_redacteur: false })
  api.myRanks.mockResolvedValue({
    voice_rank: 1,
    messages_rank: 1,
    achievements_rank: 1,
    bumps_rank: 1,
    invites_rank: 1,
    level_rank: 23,
    streak_rank: 1,
  })
})

afterEach(() => {
  cleanup()
  cookieJar.clear()
  vi.clearAllMocks()
})

describe("page /classement", () => {
  it("onglet vocal par défaut ; sept catégories ; pas de session lue pour un visiteur", async () => {
    await run()
    expect(screen.getByRole("heading", { level: 1, name: "Classement" })).toBeTruthy()
    expect(within(screen.getByRole("navigation", { name: "Catégories du classement" })).getAllByRole("link")).toHaveLength(7)
    expect(api.leaderboardVoice).toHaveBeenCalledWith(1, 10, undefined)
    expect(screen.getByText("1h 0m")).toBeTruthy()
    expect(api.getSessionUser).not.toHaveBeenCalled()
    expect(screen.queryByRole("link", { name: "Mon classement" })).toBeNull()
  })

  it("niveaux avec recherche : pas de podium, grade affiché, recherche conservée dans la pagination", async () => {
    await run({ tab: "levels", q: "ke" })
    expect(api.leaderboardLevels).toHaveBeenCalledWith(1, 10, "ke")
    expect(screen.getAllByText("Sergent Merguez").length).toBe(5)
    expect(screen.queryByRole("list", { name: "Podium" })).toBeNull()
    expect(within(screen.getByRole("table")).getAllByRole("row")).toHaveLength(5 + 1)
    expect(screen.getByRole("link", { name: "Page suivante" }).getAttribute("href")).toBe("/classement?tab=levels&page=2&q=ke")
    expect(screen.getByText(/25 résultats/)).toBeTruthy()
  })

  it("page 1 sans recherche : podium des 3 premiers, tableau à partir du 4e", async () => {
    await run({ tab: "levels" })
    expect(within(screen.getByRole("list", { name: "Podium" })).getAllByRole("listitem")).toHaveLength(3)
    expect(within(screen.getByRole("table")).getAllByRole("row")).toHaveLength(2 + 1)
  })

  it("membre connecté : sa ligne est marquée, « Mon classement » saute à la bonne page", async () => {
    cookieJar.set("better-auth.session_token", "tok")
    await run({ tab: "levels" })
    expect(api.getSessionUser).toHaveBeenCalledWith("tok")
    expect(screen.getByRole("link", { name: "Mon classement" }).getAttribute("href")).toBe("/classement?tab=levels&page=3&hl=5")
    expect(screen.getByRole("link", { name: "Cinq" }).closest("tr")!.getAttribute("data-me")).toBe("true")
  })

  it("API indisponible : message, ni tableau ni pagination", async () => {
    api.leaderboardVoice.mockRejectedValue(new Error("fetch failed"))
    await run()
    expect(screen.getByRole("status").textContent).toMatch(/indisponible/)
    expect(screen.queryByRole("table")).toBeNull()
  })

  it("classement vide : « Aucune donnée »", async () => {
    api.leaderboardVoice.mockResolvedValue({ leaderboard: [], total: 0, page: 1, limit: 10 })
    await run()
    expect(screen.getByText(/Aucune donnée/)).toBeTruthy()
  })
})
