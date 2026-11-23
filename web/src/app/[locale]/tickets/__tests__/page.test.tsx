import { cleanup, render, screen, within } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import type { TicketSummary } from "@/lib/api/types"

const cookieJar = vi.hoisted(() => new Map<string, string>())
vi.mock("next/headers", () => ({
  cookies: async () => ({ get: (name: string) => (cookieJar.has(name) ? { value: cookieJar.get(name) } : undefined) }),
}))

const api = vi.hoisted(() => ({ getSessionUser: vi.fn(), getTickets: vi.fn(), getMyTickets: vi.fn() }))
vi.mock("@/lib/api/server", () => api)

import TicketsPage from "@/app/[locale]/tickets/page"

const ticket = (id: number, over: Partial<TicketSummary> = {}): TicketSummary => ({
  id,
  ticket_number: id,
  user_id: "200",
  username: "Camille",
  subject: "Problème de rôle",
  status: "closed",
  created_at: "2026-11-10T10:00:00Z",
  closed_at: "2026-11-11T10:00:00Z",
  has_transcript: true,
  ...over,
})

const run = (params: Record<string, string | string[]> = {}) => TicketsPage({ searchParams: Promise.resolve(params) })

beforeEach(() => {
  cookieJar.set("better-auth.session_token", "tok")
  api.getSessionUser.mockResolvedValue({ user_id: "100", is_admin: false, is_redacteur: false })
  api.getMyTickets.mockResolvedValue({
    tickets: [ticket(7), ticket(8, { status: "open", closed_at: null, has_transcript: false, subject: null })],
    total: 45,
    page: 1,
    limit: 20,
  })
  api.getTickets.mockResolvedValue({ tickets: [ticket(9, { username: "Zoé" })], total: 1, page: 1, limit: 20 })
})

afterEach(() => {
  cleanup()
  cookieJar.clear()
  vi.clearAllMocks()
})

describe("page /tickets", () => {
  it("membre : ses tickets via /tickets/mine, transcription par le proxy, lue avec la session", async () => {
    render(await run())
    expect(screen.getByRole("heading", { level: 1, name: "Mes tickets" })).toBeTruthy()
    expect(screen.getByText("45 tickets")).toBeTruthy()
    const rows = within(screen.getByRole("table")).getAllByRole("row")
    expect(rows).toHaveLength(3)
    expect(within(rows[1]).getByText("#0007")).toBeTruthy()
    expect(within(rows[1]).getByText("Fermé")).toBeTruthy()
    expect(within(rows[2]).getByText("Ouvert")).toBeTruthy()
    expect(screen.queryByRole("columnheader", { name: "Membre" })).toBeNull()
    const link = screen.getByRole("link", { name: /Transcription du ticket 7/ })
    expect(link.getAttribute("href")).toBe("/api/proxy/tickets/7/transcript")
    expect(link.getAttribute("rel")).toBe("noopener noreferrer")
    expect(screen.getAllByRole("link", { name: /Transcription/ })).toHaveLength(1)
    expect(api.getMyTickets).toHaveBeenCalledWith("tok", "all", 1, 20)
    expect(api.getTickets).not.toHaveBeenCalled()
    expect(screen.queryByRole("link", { name: /tous les tickets/i })).toBeNull()
  })

  it("filtre et page de l'URL transmis à web-api ; valeurs inconnues ramenées à « tous », page 1", async () => {
    render(await run({ status: "open", page: "3" }))
    expect(api.getMyTickets).toHaveBeenLastCalledWith("tok", "open", 3, 20)
    cleanup()
    render(await run({ status: "'; DROP TABLE tickets;--", page: "-4" }))
    expect(api.getMyTickets).toHaveBeenLastCalledWith("tok", "all", 1, 20)
  })

  it("membre non administrateur : scope=all ignoré, jamais d'appel à l'historique global", async () => {
    render(await run({ scope: "all" }))
    expect(api.getTickets).not.toHaveBeenCalled()
    expect(api.getMyTickets).toHaveBeenCalled()
    expect(screen.getByRole("heading", { level: 1, name: "Mes tickets" })).toBeTruthy()
  })

  it("administrateur : ses propres tickets par défaut, avec un lien vers l'historique global", async () => {
    api.getSessionUser.mockResolvedValue({ user_id: "1", is_admin: true, is_redacteur: false })
    render(await run())
    expect(api.getMyTickets).toHaveBeenCalled()
    expect(api.getTickets).not.toHaveBeenCalled()
    expect(screen.getByRole("link", { name: /Voir tous les tickets/ }).getAttribute("href")).toBe(
      "/tickets?scope=all&status=all&page=1",
    )
  })

  it("administrateur, scope=all : historique global avec la colonne Membre, périmètre conservé dans les filtres", async () => {
    api.getSessionUser.mockResolvedValue({ user_id: "1", is_admin: true, is_redacteur: false })
    render(await run({ scope: "all", status: "closed" }))
    expect(api.getTickets).toHaveBeenCalledWith("tok", "closed", 1, 20)
    expect(api.getMyTickets).not.toHaveBeenCalled()
    expect(screen.getByRole("heading", { level: 1, name: "Tous les tickets" })).toBeTruthy()
    expect(screen.getByRole("columnheader", { name: "Membre" })).toBeTruthy()
    expect(screen.getByText("Zoé")).toBeTruthy()
    expect(screen.getByRole("link", { name: "Ouverts" }).getAttribute("href")).toBe("/tickets?scope=all&status=open&page=1")
    expect(screen.getByRole("link", { name: "Voir mes tickets" }).getAttribute("href")).toBe("/tickets?status=all&page=1")
  })

  it("API indisponible : message d'indisponibilité", async () => {
    api.getSessionUser.mockResolvedValue(null)
    render(await run())
    expect(screen.getByRole("status").textContent).toMatch(/injoignable/)
    expect(api.getMyTickets).not.toHaveBeenCalled()
  })

  it("historique illisible (null) : message d'indisponibilité, pas de tableau", async () => {
    api.getMyTickets.mockResolvedValue(null)
    render(await run())
    expect(screen.getByRole("status").textContent).toMatch(/historique est injoignable/)
    expect(screen.queryByRole("table")).toBeNull()
  })

  it("aucun ticket : message dédié, filtres conservés", async () => {
    api.getMyTickets.mockResolvedValue({ tickets: [], total: 0, page: 1, limit: 20 })
    render(await run({ status: "open" }))
    expect(screen.getByRole("status").textContent).toMatch(/aucun ticket/)
    expect(screen.getByRole("link", { name: "Ouverts" }).getAttribute("aria-current")).toBe("page")
  })
})
