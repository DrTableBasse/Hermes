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
  leaderboardGlobal: vi.fn(),
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
  api.leaderboardGlobal.mockResolvedValue({
    leaderboard: [{ user_id: "8", username: "Global", discord_avatar: null, voice_formatted: "1h 0m", total_messages: 3, achievement_count: 1, global_score: 263, global_rank: 1 }],
    total: 1,
    page: 1,
    limit: 10,
  })
  api.getSessionUser.mockResolvedValue({ user_id: "5", is_admin: false, is_redacteur: false })
  api.myRanks.mockResolvedValue({
    global_rank: 1,
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
  it("onglet global par défaut ; huit onglets, Global en premier ; pas de session lue pour un visiteur", async () => {
    await run()
    expect(screen.getByRole("heading", { level: 1, name: "Classement" })).toBeTruthy()
    const tabs = within(screen.getByRole("navigation", { name: "Catégories du classement" })).getAllByRole("link")
    expect(tabs).toHaveLength(8)
    expect(tabs[0].textContent).toBe("Global")
    expect(tabs[0].getAttribute("aria-current")).toBe("page")
    expect(api.leaderboardGlobal).toHaveBeenCalledWith(1, 10, undefined)
    expect(api.leaderboardVoice).not.toHaveBeenCalled()
    expect(screen.getByText(/263 pts/)).toBeTruthy()
    expect(screen.getByText(/200\spts par succès/)).toBeTruthy()
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

  it("paramètres répétés (?q=a&q=b) : première valeur, pas de 500", async () => {
    await ClassementPage({
      searchParams: Promise.resolve({ tab: ["levels", "voice"], q: ["a", "b"], page: ["2", "3"], hl: ["5", "6"] }),
    }).then(render)
    expect(api.leaderboardLevels).toHaveBeenCalledWith(2, 10, "a")
    expect(screen.getByText(/pour/).textContent).toContain("a")
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

  it("onglet vocal toujours accessible par ?tab=voice", async () => {
    await run({ tab: "voice" })
    expect(api.leaderboardVoice).toHaveBeenCalledWith(1, 10, undefined)
    expect(screen.getByText("1h 0m")).toBeTruthy()
  })

  it("membre connecté sur l'onglet global : « Mon classement » utilise global_rank", async () => {
    cookieJar.set("better-auth.session_token", "tok")
    api.myRanks.mockResolvedValue({ global_rank: 42, voice_rank: 1, messages_rank: 1, achievements_rank: 1, bumps_rank: 1, invites_rank: 1, level_rank: 1, streak_rank: 1 })
    await run()
    expect(screen.getByRole("link", { name: "Mon classement" }).getAttribute("href")).toBe("/classement?tab=global&page=5&hl=5")
  })

  it("API indisponible : message, ni tableau ni pagination", async () => {
    api.leaderboardGlobal.mockRejectedValue(new Error("fetch failed"))
    await run()
    expect(screen.getByRole("status").textContent).toMatch(/indisponible/)
    expect(screen.queryByRole("table")).toBeNull()
  })

  it("classement vide : « Aucune donnée »", async () => {
    api.leaderboardGlobal.mockResolvedValue({ leaderboard: [], total: 0, page: 1, limit: 10 })
    await run()
    expect(screen.getByText(/Aucune donnée/)).toBeTruthy()
  })
})
