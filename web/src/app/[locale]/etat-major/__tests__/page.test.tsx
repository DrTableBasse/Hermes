import { cleanup, render, screen, within } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import type { Game, StaffMember } from "@/lib/api/types"

const api = vi.hoisted(() => ({ getStaff: vi.fn(), getGames: vi.fn(), getPublicSettings: vi.fn() }))
vi.mock("@/lib/api/server", () => api)

import StaffPage from "@/app/[locale]/etat-major/page"

const STAFF: StaffMember[] = [
  {
    id: "100",
    name: "Saucisseur_Supreme",
    avatar: null,
    role: "GroFlex",
    grade: { name: "Général Saucisse", slug: "general", color: "#FF8A3D" },
    level: 42,
    motto: "J’ai créé ce serveur pour une soirée.",
    games: ["lol", "retired"],
  },
  {
    id: "200",
    name: "Kéfir",
    avatar: "https://cdn.discordapp.com/avatars/200/abc.png?size=1024",
    role: null,
    grade: null,
    level: null,
    motto: null,
    games: [],
  },
]

const GAMES: Game[] = [
  { key: "lol", name: "League of Legends", color: "#0AC8B9", image: null, tagline: null, players: 3, forum_url: null },
]

const TICKETS = "https://discord.com/channels/1/2"

const cards = () => screen.getAllByTestId("staff-card")

beforeEach(() => {
  api.getStaff.mockResolvedValue({ staff: STAFF })
  api.getGames.mockResolvedValue({ games: GAMES })
  api.getPublicSettings.mockResolvedValue({ invite_url: null, ticket_panel_url: TICKETS })
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe("page /etat-major", () => {
  it("une carte par gradé : rôle Discord, grade, niveau, phrase, jeux actifs, bouton ticket", async () => {
    render(await StaffPage())
    expect(screen.getByRole("heading", { level: 1, name: "L’état-major" })).toBeTruthy()
    expect(cards()).toHaveLength(2)

    const first = within(cards()[0])
    expect(first.getByRole("heading", { name: "Saucisseur_Supreme" })).toBeTruthy()
    expect(first.getByText("GroFlex")).toBeTruthy()
    expect(first.getByText("Général Saucisse")).toBeTruthy()
    expect(first.getByText(/niveau 42/)).toBeTruthy()
    // Guillemets français tenus par des espaces insécables : jamais de « » orphelin en bout de ligne.
    const nbsp = String.fromCharCode(0xa0)
    expect(first.getByText(/J’ai créé ce serveur/).textContent).toBe(`«${nbsp}J’ai créé ce serveur pour une soirée.${nbsp}»`)
    // Nom du jeu lu dans /games ; une clé inconnue (jeu retiré) n'est pas affichée.
    expect(first.getByRole("list", { name: "Jeux de Saucisseur_Supreme" }).textContent).toBe("League of Legends")
    expect(first.getByRole("link", { name: "Contacter via un ticket" }).getAttribute("href")).toBe(TICKETS)
    expect(screen.queryByText(/newticket/)).toBeNull()
  })

  it("membre sans grade ni phrase (base muette) : rien d'inventé", async () => {
    render(await StaffPage())
    const second = within(cards()[1])
    expect(second.getByRole("heading", { name: "Kéfir" })).toBeTruthy()
    expect(second.queryByText(/niveau/)).toBeNull()
    expect(second.queryByText(/«/)).toBeNull()
    expect(second.queryByRole("list")).toBeNull()
    // Avatar Discord ramené à la taille affichée.
    expect(cards()[1].querySelector("img")!.getAttribute("src")).toContain("size=128")
  })

  it("salon de tickets non réglé : pas de bouton, explication /newticket", async () => {
    api.getPublicSettings.mockResolvedValue({ invite_url: null, ticket_panel_url: null })
    render(await StaffPage())
    expect(screen.queryByRole("link", { name: "Contacter via un ticket" })).toBeNull()
    expect(screen.getByText((_, el) => el?.tagName === "P" && /tape \/newticket sur le Discord/.test(el.textContent ?? ""))).toBeTruthy()
  })

  it("liste périmée : cartes du dernier relevé et avertissement", async () => {
    api.getStaff.mockResolvedValue({ staff: STAFF, stale: true })
    render(await StaffPage())
    expect(cards()).toHaveLength(2)
    expect(screen.getByRole("status").textContent).toMatch(/dernier état-major connu/)
  })

  it("API indisponible : message d'indisponibilité, aucune carte", async () => {
    api.getStaff.mockResolvedValue(null)
    api.getGames.mockResolvedValue(null)
    api.getPublicSettings.mockResolvedValue(null)
    render(await StaffPage())
    expect(screen.queryAllByTestId("staff-card")).toHaveLength(0)
    expect(screen.getByRole("status").textContent).toMatch(/injoignable/)
  })

  it("bot muet sans liste connue (staff vide et périmé) : indisponible, pas « aucun gradé »", async () => {
    api.getStaff.mockResolvedValue({ staff: [], stale: true })
    render(await StaffPage())
    expect(screen.getByRole("status").textContent).toMatch(/injoignable/)
  })
})
