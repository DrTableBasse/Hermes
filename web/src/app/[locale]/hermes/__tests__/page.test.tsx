import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import type { HermesStatus } from "@/lib/api/types"

const api = vi.hoisted(() => ({ getHermesStatus: vi.fn(), getGames: vi.fn() }))
vi.mock("@/lib/api/server", () => api)

import HermesPage from "@/app/[locale]/hermes/page"
import { LOG_INTERVAL_MAX_MS, LOG_INTERVAL_MIN_MS } from "@/components/hermes/absurd-console"
import { BOT_COMMANDS, GAME_COMMAND_COMMENTS } from "@/content/commands"
import { HERMES_LOGS } from "@/content/hermes-logs"

function curve(values: Array<number | null>) {
  return values.map((messages, i) => ({ hour: new Date(Date.UTC(2026, 10, 20, i)).toISOString(), messages }))
}

const STATUS: HermesStatus = {
  online: true,
  latency_ms: 42.4,
  availability: { percent: 99.97, since: "2026-10-01T08:00:00Z" },
  commands_served: 182_400,
  today: { xp_distributed: null, achievements: 27, tickets: 0, bump_reminders: null },
  daily_curve: curve([10, null, 30, 40]),
}

/** Faux `matchMedia` : `reduced` règle la réponse à `prefers-reduced-motion: reduce`. */
function mockMotion(reduced: boolean) {
  window.matchMedia = vi.fn().mockImplementation((q: string) => ({
    matches: reduced && q.includes("reduce"),
    media: q,
    addEventListener: () => {},
    removeEventListener: () => {},
  })) as unknown as typeof window.matchMedia
}

const logLines = () => within(screen.getByTestId("hermes-console")).getAllByRole("listitem")

const game = (key: string, name: string, command_name: string | null) => ({
  key, name, color: "#000000", image: null, tagline: null, players: null, forum_url: null, command_name,
})

beforeEach(() => {
  api.getHermesStatus.mockResolvedValue(STATUS)
  api.getGames.mockResolvedValue({
    games: [game("dbd", "Dead by Daylight", "dbd"), game("war-dogs", "War Dogs", null), game("apex", "Apex Legends", "apex")],
  })
  mockMotion(false)
})

afterEach(() => {
  cleanup()
  vi.useRealTimers()
  vi.clearAllMocks()
})

describe("page /hermes", () => {
  it("rend le tableau de bord avec les vraies valeurs", async () => {
    render(await HermesPage())
    expect(screen.getByRole("heading", { level: 1, name: "Hermes, notre bot maison" })).toBeTruthy()
    expect(screen.getByTestId("hermes-status").textContent).toBe("En ligne")
    const tiles = screen.getByTestId("hermes-tiles")
    expect(within(tiles).getByText("42 ms")).toBeTruthy()
    expect(within(tiles).getByText("99,97 %")).toBeTruthy()
    expect(within(tiles).getByText("182 400")).toBeTruthy()
  })

  it("rapport du jour : lignes à null masquées, zéro réel affiché, courbe sans heure inventée", async () => {
    render(await HermesPage())
    const report = screen.getByTestId("hermes-report")
    expect(within(report).getByText("Succès débloqués")).toBeTruthy()
    expect(within(report).getByText("27")).toBeTruthy()
    expect(within(report).getByText("Tickets ouverts")).toBeTruthy()
    expect(within(report).getByText("0")).toBeTruthy()
    expect(within(report).queryByText("XP distribuée")).toBeNull()
    expect(within(report).queryByText("Rappels de bump envoyés")).toBeNull()
    expect(within(report).getByText("80")).toBeTruthy()
    expect(screen.getByTestId("hermes-spark").querySelectorAll("rect")).toHaveLength(3)
  })

  it("disponibilité inconnue : « en service depuis le JJ/MM » ; valeurs null : tuiles masquées", async () => {
    api.getHermesStatus.mockResolvedValue({
      ...STATUS,
      online: false,
      latency_ms: null,
      commands_served: null,
      availability: { percent: null, since: "2026-11-15T09:00:00Z" },
    })
    render(await HermesPage())
    expect(screen.getByTestId("hermes-status").textContent).toMatch(/Hors ligne/)
    const tiles = screen.getByTestId("hermes-tiles")
    expect(within(tiles).getByText("En service depuis le 15/11")).toBeTruthy()
    expect(within(tiles).queryByText("Temps de réponse")).toBeNull()
    expect(within(tiles).queryByText("Commandes servies")).toBeNull()
  })

  it("reste debout quand web-api est indisponible", async () => {
    api.getHermesStatus.mockResolvedValue(null)
    api.getGames.mockResolvedValue(null)
    render(await HermesPage())
    expect(screen.getByRole("heading", { level: 1 })).toBeTruthy()
    expect(screen.getByTestId("hermes-status").textContent).toBe("Hermes ne répond pas")
    expect(screen.queryByTestId("hermes-tiles")).toBeNull()
    expect(screen.getByText(/Tableau de bord indisponible/)).toBeTruthy()
    expect(screen.getByText(/Rapport indisponible/)).toBeTruthy()
    // Console et commandes sont du contenu statique : toujours là.
    expect(logLines()).toHaveLength(8)
    expect(screen.getByText("/rang")).toBeTruthy()
    expect(screen.queryByText("/dbd")).toBeNull()
  })

  it("signale un statut périmé", async () => {
    api.getHermesStatus.mockResolvedValue({ ...STATUS, stale: true })
    render(await HermesPage())
    expect(screen.getByTestId("hermes-status").textContent).toMatch(/dernières valeurs connues/)
  })

  it("liste toutes les commandes du bot et signale celles du staff", async () => {
    render(await HermesPage())
    for (const c of BOT_COMMANDS) expect(screen.getByText(`/${c.name}`)).toBeTruthy()
    const kick = screen.getByText("/kick").closest("li") as HTMLElement
    expect(within(kick).getByText("Staff")).toBeTruthy()
    const rang = screen.getByText("/rang").closest("li") as HTMLElement
    expect(within(rang).queryByText("Staff")).toBeNull()
    expect(screen.getByRole("heading", { level: 3, name: "Réservées au staff" })).toBeTruthy()
  })

  it("commandes de jeux : celles des jeux actifs, en tête de « Jeux et détente », commentées", async () => {
    render(await HermesPage())
    const section = within(screen.getByRole("region", { name: "Jeux et détente" }))
    const names = section.getAllByRole("listitem").map(li => li.querySelector("code")?.textContent)
    expect(names.slice(0, 2)).toEqual(["/dbd", "/apex"])
    expect(names).toContain("/blague")
    const dbd = screen.getByText("/dbd").closest("li") as HTMLElement
    expect(within(dbd).getByText(GAME_COMMAND_COMMENTS.dbd)).toBeTruthy()
    const apex = screen.getByText("/apex").closest("li") as HTMLElement
    expect(within(apex).getByText(/Appelle les joueurs de Apex Legends/)).toBeTruthy()
    // War Dogs n'est pas provisionné : aucune commande.
    expect(screen.queryByText("/war-dogs")).toBeNull()
  })
})

describe("console d'Hermes", () => {
  it("ajoute une ligne à chaque intervalle, garde une fenêtre de 11 lignes, met en pause au survol", async () => {
    vi.useFakeTimers()
    render(await HermesPage())
    expect(logLines()).toHaveLength(8)
    for (const line of logLines()) {
      expect(HERMES_LOGS.some(l => line.textContent?.endsWith(l.text))).toBe(true)
      expect(line.textContent).toMatch(/^\[\d{2}:\d{2}:\d{2}\] /)
    }

    // Rien avant le délai minimal, une ligne au plus tard au délai maximal.
    act(() => vi.advanceTimersByTime(LOG_INTERVAL_MIN_MS - 1))
    expect(logLines()).toHaveLength(8)
    act(() => vi.advanceTimersByTime(LOG_INTERVAL_MAX_MS - LOG_INTERVAL_MIN_MS + 1))
    expect(logLines()).toHaveLength(9)
    act(() => vi.advanceTimersByTime(LOG_INTERVAL_MAX_MS * 10))
    expect(logLines()).toHaveLength(11)

    const console = screen.getByTestId("hermes-console")
    fireEvent.mouseEnter(console)
    const before = logLines().map(l => l.textContent)
    act(() => vi.advanceTimersByTime(LOG_INTERVAL_MAX_MS * 3))
    expect(logLines().map(l => l.textContent)).toEqual(before)
    fireEvent.mouseLeave(console)
    act(() => vi.advanceTimersByTime(LOG_INTERVAL_MAX_MS))
    expect(logLines().map(l => l.textContent)).not.toEqual(before)
  })

  it("revient à la ligne au lieu de tronquer un message long", async () => {
    render(await HermesPage())
    for (const line of logLines()) {
      expect(line.className).toContain("break-words")
      expect(line.className).not.toContain("whitespace-nowrap")
      expect(line.className).not.toContain("text-ellipsis")
    }
  })

  it("reste figée sous mouvement réduit", async () => {
    mockMotion(true)
    vi.useFakeTimers()
    render(await HermesPage())
    const before = logLines().map(l => l.textContent)
    act(() => vi.advanceTimersByTime(LOG_INTERVAL_MAX_MS * 5))
    expect(logLines().map(l => l.textContent)).toEqual(before)
    expect(screen.getByTestId("hermes-console").dataset.paused).toBe("true")
  })
})
