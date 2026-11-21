import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import type { StaffMember } from "@/lib/api/types"

const cookieJar = vi.hoisted(() => new Map<string, string>())
vi.mock("next/headers", () => ({
  cookies: async () => ({ get: (name: string) => (cookieJar.has(name) ? { value: cookieJar.get(name) } : undefined) }),
}))

const api = vi.hoisted(() => ({ getSessionUser: vi.fn(), getStaff: vi.fn(), getGames: vi.fn() }))
vi.mock("@/lib/api/server", () => api)
vi.mock("@/lib/api/client", () => ({ api: { staff: { updateMyProfile: vi.fn() } }, ApiError: class extends Error {} }))

import ProfilePage from "@/app/[locale]/profil/page"

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

  it("membre hors staff : message neutre, pas de formulaire", async () => {
    api.getSessionUser.mockResolvedValue({ user_id: "999", is_admin: false, is_redacteur: false })
    render(await ProfilePage())
    expect(screen.queryByRole("form")).toBeNull()
    expect(screen.queryByLabelText("Ta phrase")).toBeNull()
    expect(screen.getByRole("status").textContent).toMatch(/arrive bientôt/)
  })

  it("API indisponible : message d'indisponibilité, pas de formulaire", async () => {
    api.getSessionUser.mockResolvedValue(null)
    api.getStaff.mockResolvedValue(null)
    api.getGames.mockResolvedValue(null)
    render(await ProfilePage())
    expect(screen.queryByLabelText("Ta phrase")).toBeNull()
    expect(screen.getByRole("status").textContent).toMatch(/injoignable/)
  })

  it("liste des jeux périmée : formulaire sans cases, jeux conservés", async () => {
    api.getGames.mockResolvedValue({ games: [], stale: true })
    render(await ProfilePage())
    expect(screen.queryAllByRole("checkbox")).toHaveLength(0)
    expect(screen.getByText(/Liste des jeux indisponible/)).toBeTruthy()
  })
})
