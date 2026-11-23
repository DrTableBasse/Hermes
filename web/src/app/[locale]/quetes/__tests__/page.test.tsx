import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import type { Quest } from "@/lib/api/types"

const cookieJar = vi.hoisted(() => new Map<string, string>())
vi.mock("next/headers", () => ({
  cookies: async () => ({ get: (name: string) => (cookieJar.has(name) ? { value: cookieJar.get(name) } : undefined) }),
}))

const api = vi.hoisted(() => ({ getSessionUser: vi.fn(), getWeeklyQuests: vi.fn() }))
vi.mock("@/lib/api/server", () => api)
vi.mock("@/lib/api/client", () => ({ api: { quests: { claim: vi.fn() } } }))

import QuestsPage from "@/app/[locale]/quetes/page"

const quest = (id: number, over: Partial<Quest> = {}): Quest => ({
  id,
  title: `Quête ${id}`,
  description: "Envoyer des messages",
  quest_type: "messages",
  target_value: 50,
  xp_reward: 200,
  icon: null,
  current_progress: 20,
  status: "active",
  week_start: "2026-11-16",
  week_end: "2026-11-22",
  is_active: true,
  ...over,
})

beforeEach(() => {
  cookieJar.set("better-auth.session_token", "tok")
  api.getSessionUser.mockResolvedValue({ user_id: "100", is_admin: false, is_redacteur: false })
  api.getWeeklyQuests.mockResolvedValue([quest(1), quest(2, { status: "completed", current_progress: 50 })])
})

afterEach(() => {
  cleanup()
  cookieJar.clear()
  vi.clearAllMocks()
})

describe("page /quetes", () => {
  it("liste les quêtes avec leur avancement et propose la récompense de celle qui est terminée", async () => {
    render(await QuestsPage())
    expect(screen.getByRole("heading", { level: 1, name: "Défis de la semaine" })).toBeTruthy()
    expect(screen.getAllByRole("listitem")).toHaveLength(2)
    expect(screen.getByText("20 sur 50")).toBeTruthy()
    expect(screen.getAllByRole("button", { name: "Réclamer la récompense" })).toHaveLength(1)
    expect(api.getWeeklyQuests).toHaveBeenCalledWith("tok")
  })

  it("aucune quête active : message dédié", async () => {
    api.getWeeklyQuests.mockResolvedValue([])
    render(await QuestsPage())
    expect(screen.getByRole("status").textContent).toMatch(/Aucun défi actif/)
  })

  it("API indisponible : message d'indisponibilité, pas de liste", async () => {
    api.getSessionUser.mockResolvedValue(null)
    render(await QuestsPage())
    expect(screen.getByRole("status").textContent).toMatch(/injoignables/)
    expect(screen.queryAllByRole("listitem")).toHaveLength(0)
    expect(api.getWeeklyQuests).not.toHaveBeenCalled()
  })

  it("quêtes illisibles (null) : message d'indisponibilité", async () => {
    api.getWeeklyQuests.mockResolvedValue(null)
    render(await QuestsPage())
    expect(screen.getByRole("status").textContent).toMatch(/injoignables/)
  })
})
