import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import type { StaffMember, UserStats } from "@/lib/api/types"

const cookieJar = vi.hoisted(() => new Map<string, string>())
vi.mock("next/headers", () => ({
  cookies: async () => ({ get: (name: string) => (cookieJar.has(name) ? { value: cookieJar.get(name) } : undefined) }),
}))

const api = vi.hoisted(() => ({
  getSessionUser: vi.fn(),
  getStaff: vi.fn(),
  getGames: vi.fn(),
  getUserStats: vi.fn(),
  getXp: vi.fn(),
  getUserAchievementsAll: vi.fn(),
  getAchievementCatalog: vi.fn(),
}))
vi.mock("@/lib/api/server", () => api)
vi.mock("@/lib/api/client", () => ({ api: { staff: { updateMyProfile: vi.fn() } }, ApiError: class extends Error {} }))

import ProfilePage from "@/app/[locale]/profil/page"

const STATS: UserStats = {
  user: { user_id: "100", username: "kefir", nickname: "Kéfir", discord_avatar: null, last_seen: "2026-11-19T10:00:00Z" },
  stats: {
    total_messages: 1284,
    voice_hours: 46.5,
    warn_count: 0,
    msg_rank: 12,
    voice_rank: 3,
    xp_total: 21300,
    current_level: 14,
    current_streak: 9,
    max_streak: 20,
    xp_multiplier: 1.2,
    bump_count: 5,
    bump_rank: 7,
    msg_current_streak: 0,
    msg_max_streak: 4,
  },
  achievements: [],
}

const ME: StaffMember = {
  id: "100",
  name: "Kéfir",
  avatar: null,
  role: "Modération",
  grade: null,
  level: 3,
  motto: "Je veille sur le vocal.",
  games: ["lol"],
}

beforeEach(() => {
  cookieJar.set("__Secure-better-auth.session_token", "tok")
  api.getSessionUser.mockResolvedValue({ user_id: "100", is_admin: false, is_redacteur: false })
  api.getStaff.mockResolvedValue({ staff: [ME] })
  api.getUserStats.mockResolvedValue(STATS)
  api.getXp.mockResolvedValue({
    user_id: "100",
    total_xp: 21300,
    weekly_xp: 10,
    current_level: 14,
    grade: { name: "Caporal Saucisse", slug: "caporal", color: "#E8B86B" },
  })
  api.getAchievementCatalog.mockResolvedValue({
    members_total: 4,
    achievements: [{ id: 1, name: "Premier cri", description: "Un message", icon: "🏅", points: 10, condition_type: "messages", unlocked_count: 0 }],
  })
  api.getUserAchievementsAll.mockResolvedValue([
    { id: 1, name: "Premier cri", description: "Un message", icon: "🏅", points: 10, condition_type: "messages", unlocked: true, unlocked_at: "2026-11-01T10:00:00Z" },
  ])
  api.getGames.mockResolvedValue({
    games: [{ key: "lol", name: "League of Legends", color: "#0AC8B9", image: null, tagline: null, players: null, forum_url: null }],
  })
})

afterEach(() => {
  cleanup()
  cookieJar.clear()
  vi.clearAllMocks()
})

describe("page /profil", () => {
  it("membre du staff : formulaire prérempli, liste du staff lue hors cache avec la session", async () => {
    render(await ProfilePage())
    expect(screen.getByRole("heading", { level: 2, name: "Ta carte de l’état-major" })).toBeTruthy()
    expect((screen.getByLabelText("Ta phrase") as HTMLTextAreaElement).value).toBe("Je veille sur le vocal.")
    expect((screen.getByRole("checkbox", { name: "League of Legends" }) as HTMLInputElement).checked).toBe(true)
    expect(api.getStaff).toHaveBeenCalledWith("tok")
    expect(api.getSessionUser).toHaveBeenCalledWith("tok")
  })

  it("membre hors staff : pas de formulaire, mais sa fiche reste affichée", async () => {
    api.getSessionUser.mockResolvedValue({ user_id: "999", is_admin: false, is_redacteur: false })
    render(await ProfilePage())
    expect(screen.queryByRole("form")).toBeNull()
    expect(screen.queryByLabelText("Ta phrase")).toBeNull()
    expect(screen.queryByRole("status")).toBeNull()
    expect(screen.getByRole("heading", { level: 2, name: "Kéfir" })).toBeTruthy()
  })

  it("fiche : grade, niveau, XP, statistiques et succès, lus avec la session et l'identifiant de /auth/me", async () => {
    render(await ProfilePage())
    expect(screen.getByText("Caporal Saucisse")).toBeTruthy()
    expect(screen.getByText("niveau 14")).toBeTruthy()
    expect(screen.getByText(/21\s300 XP/)).toBeTruthy()
    expect(screen.getByText("46 h 30")).toBeTruthy()
    expect(screen.getByText("Casier vierge")).toBeTruthy()
    expect(screen.getByText(/×1\.2 XP · record 20 j/)).toBeTruthy()
    expect(screen.getByText("Envoie un message")).toBeTruthy()
    expect(screen.getByText("Premier cri")).toBeTruthy()
    // Rareté réelle (0 % des membres → Légendaire), plus le palier de points (10 pts → Commun).
    expect(screen.getByText("Légendaire")).toBeTruthy()
    expect(api.getUserStats).toHaveBeenCalledWith("100", "tok")
    expect(api.getXp).toHaveBeenCalledWith("100", "tok")
    expect(screen.getByRole("link", { name: "Voir mon profil public" }).getAttribute("href")).toBe("/u/100")
  })

  it("statistiques indisponibles : note, la carte du staff reste modifiable", async () => {
    api.getUserStats.mockRejectedValue(new Error("503 /users/100/stats"))
    api.getXp.mockResolvedValue(null)
    api.getUserAchievementsAll.mockRejectedValue(new Error("503"))
    render(await ProfilePage())
    expect(screen.getByRole("status").textContent).toMatch(/statistiques sont injoignables/)
    expect(screen.getByLabelText("Ta phrase")).toBeTruthy()
  })

  it("grade inconnu (/xp muet) : la fiche s'affiche sans pastille de grade", async () => {
    api.getXp.mockResolvedValue(null)
    render(await ProfilePage())
    expect(screen.getByText("niveau 14")).toBeTruthy()
    expect(screen.queryByText("Caporal Saucisse")).toBeNull()
  })

  it("API indisponible : message d'indisponibilité, pas de formulaire", async () => {
    api.getSessionUser.mockResolvedValue(null)
    api.getStaff.mockResolvedValue(null)
    api.getGames.mockResolvedValue(null)
    render(await ProfilePage())
    expect(screen.queryByLabelText("Ta phrase")).toBeNull()
    expect(screen.getByRole("status").textContent).toMatch(/injoignable/)
  })

  it("liste du staff périmée : pas de formulaire prérempli de vide, note « Hermes injoignable »", async () => {
    api.getStaff.mockResolvedValue({ staff: [{ ...ME, motto: null, games: [] }], stale: true })
    render(await ProfilePage())
    expect(screen.queryByLabelText("Ta phrase")).toBeNull()
    expect(screen.queryByRole("button", { name: "Enregistrer" })).toBeNull()
    expect(screen.getByRole("status").textContent).toMatch(/Hermes est injoignable.*Réessaie plus tard/)
  })

  it("liste des jeux périmée : formulaire sans cases, jeux conservés", async () => {
    api.getGames.mockResolvedValue({ games: [], stale: true })
    render(await ProfilePage())
    expect(screen.queryAllByRole("checkbox")).toHaveLength(0)
    expect(screen.getByText(/Liste des jeux indisponible/)).toBeTruthy()
  })
})
