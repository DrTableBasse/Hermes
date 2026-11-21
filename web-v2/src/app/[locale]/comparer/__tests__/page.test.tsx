import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const api = vi.hoisted(() => ({ getUserPublicStats: vi.fn() }))
vi.mock("@/lib/api/server", () => api)

import ComparePage from "@/app/[locale]/comparer/page"

const GRADE = { name: "Sergent Merguez", slug: "sergent", color: "#FF8A3D" }
const user = (id: string, name: string, level: number, bumps: number) => ({
  user_id: id,
  username: name,
  nickname: null,
  discord_avatar: null,
  stats: {
    total_messages: 10,
    voice_seconds: 60,
    voice_formatted: "1h 0m",
    total_xp: level * 100,
    current_level: level,
    grade: GRADE,
    achievement_count: 2,
    current_streak: 0,
    bump_count: bumps,
  },
  achievements: [],
})

const run = (sp: { u1?: string; u2?: string }) => ComparePage({ searchParams: Promise.resolve(sp) }).then(render)

beforeEach(() => {
  api.getUserPublicStats.mockImplementation(async (id: string) => {
    if (id === "1") return user("1", "Alpha", 10, 3)
    if (id === "2") return user("2", "Bravo", 5, 3)
    throw new Error(`404 /users/${id}/public`)
  })
})
afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe("page /comparer", () => {
  it("sans paramètres : explication, aucun appel", async () => {
    await run({})
    expect(screen.getByText(/identifiants Discord/)).toBeTruthy()
    expect(api.getUserPublicStats).not.toHaveBeenCalled()
  })

  it("compare deux membres : gagnant marqué, égalité sans gagnant, grade affiché", async () => {
    await run({ u1: "1", u2: "2" })
    expect(screen.getByRole("heading", { level: 1, name: "Comparaison" })).toBeTruthy()
    expect(screen.getAllByText("Sergent Merguez")).toHaveLength(2)
    const level = screen.getByRole("row", { name: /Niveau/ })
    expect(level.querySelectorAll("[data-win]")).toHaveLength(1)
    expect(level.querySelector("td")!.getAttribute("data-win")).toBe("true")
    expect(screen.getByRole("row", { name: /Bumps/ }).querySelectorAll("[data-win]")).toHaveLength(0)
  })

  it("paramètres répétés (?u1=1&u1=9) : première valeur", async () => {
    await ComparePage({ searchParams: Promise.resolve({ u1: ["1", "999"], u2: ["2"] }) }).then(render)
    expect(api.getUserPublicStats).toHaveBeenCalledWith("1")
    expect(api.getUserPublicStats).not.toHaveBeenCalledWith("999")
    expect(screen.getByRole("heading", { level: 1, name: "Comparaison" })).toBeTruthy()
  })

  it("membre inconnu : nommé dans le message", async () => {
    await run({ u1: "1", u2: "999" })
    expect(screen.getByRole("status").textContent).toBe("Membre 999 introuvable.")
  })

  it("aucun des deux trouvé ; identifiant invalide traité comme inconnu sans appel", async () => {
    await run({ u1: "998", u2: ".." })
    expect(screen.getByRole("status").textContent).toMatch(/Aucun des deux/)
    expect(api.getUserPublicStats).not.toHaveBeenCalledWith("..")
  })

  it("API indisponible : ni « introuvable » ni comparaison", async () => {
    api.getUserPublicStats.mockRejectedValue(new Error("fetch failed"))
    await run({ u1: "1", u2: "2" })
    expect(screen.getByRole("status").textContent).toMatch(/ne répond pas/)
  })
})
