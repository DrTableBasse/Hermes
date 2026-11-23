import { act, cleanup, render, screen, within } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { PERMISSIONS } from "@/lib/permissions"

vi.mock("server-only", () => ({}))
vi.mock("next/headers", () => ({ cookies: async () => ({ get: () => ({ value: "tok" }) }) }))
vi.mock("next/navigation", () => ({ useSearchParams: () => new URLSearchParams() }))

const api = vi.hoisted(() => {
  const names = [
    "getSessionUser", "getAdminStats", "getAdminCommands", "getAdminSettings", "getDiscordChannels",
    "getDiscordRoles", "getAdminGames", "getAdminGallery", "getQuestTemplates", "getActiveQuests",
    "getAnalytics", "getPageFresh", "getGradesFresh", "getTickets", "getStaff", "getGames",
  ]
  return Object.fromEntries(names.map(n => [n, vi.fn()]))
})
vi.mock("@/lib/api/server", () => api)

const client = vi.hoisted(() => ({
  api: { admin: { allWarns: vi.fn(), audit: vi.fn(), auditFacets: vi.fn() } },
  auditCsvUrl: () => "/api/proxy/admin/audit.csv",
  ApiError: class extends Error {},
}))
vi.mock("@/lib/api/client", () => client)

import AdminHome from "@/app/[locale]/admin/page"
import AnalyticsPage from "@/app/[locale]/admin/analytique/page"
import CommandsPage from "@/app/[locale]/admin/commandes/page"
import ContentPage from "@/app/[locale]/admin/contenus/page"
import StaffPage from "@/app/[locale]/admin/etat-major/page"
import GalleryPage from "@/app/[locale]/admin/galerie/page"
import GamesPage from "@/app/[locale]/admin/jeux/page"
import ModerationPage from "@/app/[locale]/admin/moderation/page"
import QuestsPage from "@/app/[locale]/admin/quetes/page"
import SettingsPage from "@/app/[locale]/admin/reglages/page"
import TicketsPage from "@/app/[locale]/admin/tickets/page"

const item = (key: string, kind: string, value: string, resolved: unknown = null, can_create = false) => ({
  key, label: `Libellé ${key}`, kind, value, can_create, resolved,
})

const SETTINGS = {
  groups: [
    { name: "Salons", items: [item("ticket_panel_channel", "channel", "55", { id: "55", name: null, exists: false }, true)] },
    { name: "Rôles", items: [item("mod_role", "role", "Modération")] },
    { name: "Site", items: [item("invite_url", "url", "https://discord.gg/abc")] },
  ],
}

beforeEach(() => {
  for (const fn of Object.values(api)) fn.mockResolvedValue(null)
  api.getSessionUser.mockResolvedValue({
    user_id: "1",
    is_admin: true,
    is_redacteur: true,
    permissions: Object.keys(PERMISSIONS).sort(),
  })
  client.api.admin.allWarns.mockResolvedValue({ warns: [] })
  client.api.admin.audit.mockResolvedValue({ events: [], total: 0, page: 1, pages: 1 })
  client.api.admin.auditFacets.mockResolvedValue({ kinds: {}, channels: [] })
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe("sous-pages admin : rendu et erreurs de l’API", () => {
  it("vue d’ensemble : statistiques et réglages importants avec leur état", async () => {
    api.getAdminStats.mockResolvedValue({ members: 1234, total_messages: 5, total_warns: 2, total_articles: 3 })
    api.getAdminSettings.mockResolvedValue(SETTINGS)
    render(await AdminHome())
    expect(api.getAdminStats).toHaveBeenCalledWith("tok")
    expect(screen.getByText("Membres").nextElementSibling?.textContent).toMatch(/1\s?234/)
    const keys = within(screen.getByRole("region", { name: "Réglages à vérifier" }))
    expect(keys.getByText("Introuvable sur Discord")).toBeTruthy() // ticket_panel_channel
    expect(keys.getByText("À choisir")).toBeTruthy() // mod_role : nom par défaut, aucun rôle choisi
    expect(keys.getByText("Réglé")).toBeTruthy() // invite_url
    expect(keys.getByRole("link", { name: "Libellé invite_url" }).getAttribute("href")).toBe("/admin/reglages#setting-invite_url")
  })

  it("vue d’ensemble : API muette → messages d’erreur, pas de zéros", async () => {
    render(await AdminHome())
    expect(screen.getByText(/Statistiques du serveur indisponibles/)).toBeTruthy()
    expect(screen.getByText(/Réglages illisibles/)).toBeTruthy()
    expect(screen.queryByText("0")).toBeNull()
  })

  it("réglages : une carte par groupe ; bot muet signalé ; API muette → erreur", async () => {
    api.getAdminSettings.mockResolvedValue(SETTINGS)
    render(await SettingsPage())
    expect(screen.getAllByRole("heading", { level: 2 }).map(h => h.textContent)).toEqual(["Salons", "Rôles", "Site"])
    expect(screen.getByText(/Hermes ne répond pas : les listes/)).toBeTruthy()
    cleanup()
    api.getAdminSettings.mockResolvedValue(null)
    render(await SettingsPage())
    expect(screen.getByRole("alert").textContent).toMatch(/Réglages illisibles/)
  })

  it("commandes : interrupteurs triés avec description ; bot muet → erreur", async () => {
    api.getAdminCommands.mockResolvedValue({ commands: { rank: true, ban: false }, descriptions: { rank: "Ton rang" } })
    render(await CommandsPage())
    const switches = screen.getAllByRole("switch")
    expect(switches.map(s => s.getAttribute("aria-label"))).toEqual(["/ban", "/rank"])
    expect(switches[0].getAttribute("aria-checked")).toBe("false")
    expect(screen.getByText("Ton rang")).toBeTruthy()
    cleanup()
    api.getAdminCommands.mockResolvedValue(null)
    render(await CommandsPage())
    expect(screen.getByText(/liste des commandes est indisponible/)).toBeTruthy()
  })

  it("galerie : éléments masqués signalés ; API muette → erreur", async () => {
    api.getAdminGallery.mockResolvedValue([
      { id: 1, kind: "image", url: "/media/gallery/a.png", provider: null, caption: "Raid", hidden: true,
        author: { id: "2", name: "Zoé", avatar: null }, created_at: null },
    ])
    render(await GalleryPage())
    expect(screen.getByText("Masqué")).toBeTruthy()
    expect(screen.getByRole("button", { name: "Afficher" })).toBeTruthy()
    cleanup()
    render(await (api.getAdminGallery.mockResolvedValue(null), GalleryPage()))
    expect(screen.getByText(/Galerie illisible/)).toBeTruthy()
  })

  it("tickets : historique global avec membre et transcription ; API muette → erreur", async () => {
    api.getTickets.mockResolvedValue({
      tickets: [{ id: 9, ticket_number: 9, user_id: "2", username: "Zoé", subject: null, status: "open",
        created_at: null, closed_at: null, has_transcript: true }],
      total: 1, page: 1, limit: 20,
    })
    render(await TicketsPage({ searchParams: Promise.resolve({ status: "open", page: "2" }) }))
    expect(api.getTickets).toHaveBeenCalledWith("tok", "open", 2, 20)
    expect(screen.getByText("Zoé")).toBeTruthy()
    expect(screen.getByRole("link", { name: /Transcription du ticket 9/ }).getAttribute("href")).toBe("/api/proxy/tickets/9/transcript")
    cleanup()
    api.getTickets.mockResolvedValue(null)
    render(await TicketsPage({ searchParams: Promise.resolve({}) }))
    expect(screen.getByText(/injoignable/)).toBeTruthy()
  })

  it("analytique : indicateurs ; API muette → erreur", async () => {
    api.getAnalytics.mockResolvedValue({
      actions_14d: [{ date: "2026-11-20", label: "11-20", warn: 2, kick: 0, ban: 1, timeout: 0 }],
      level_distribution: [{ level_range: "1-5", count: 40 }],
      quest_completion: [],
      top_xp_weekly: [{ username: "Zoé", weekly_xp: 900 }],
      summary: { active_members: 50, total_messages: 1000, warns_30d: 3, quests_done_7d: 7 },
    })
    render(await AnalyticsPage())
    expect(screen.getByText("Avertissements (2)")).toBeTruthy()
    expect(screen.getByText("Aucune quête active cette semaine.")).toBeTruthy()
    expect(screen.getByText("900 XP")).toBeTruthy()
    cleanup()
    api.getAnalytics.mockResolvedValue(null)
    render(await AnalyticsPage())
    expect(screen.getByText(/Analytique indisponible/)).toBeTruthy()
  })

  it("modération : sanctions et journal lus au chargement ; échec signalé", async () => {
    client.api.admin.allWarns.mockRejectedValue(new Error("réseau"))
    await act(async () => {
      render(await ModerationPage())
    })
    expect(screen.getByRole("heading", { name: "Sanctionner un membre" })).toBeTruthy()
    expect(client.api.admin.audit).toHaveBeenCalledWith({}, 1)
    expect(screen.getByText(/Le site ne répond pas/)).toBeTruthy()
    expect(screen.getByText("Aucun évènement pour ces filtres.")).toBeTruthy()
  })

  it("quêtes : bibliothèque et semaine ; échecs séparés", async () => {
    api.getQuestTemplates.mockResolvedValue([
      { id: 1, title: "Bavard", description: null, quest_type: "messages", target_value: 100, xp_reward: 50, icon: "💬", is_enabled: true },
    ])
    render(await QuestsPage())
    expect(screen.getByText("Bavard")).toBeTruthy()
    expect(screen.getByText(/Quêtes de la semaine illisibles/)).toBeTruthy()
    cleanup()
    api.getQuestTemplates.mockResolvedValue(null)
    api.getActiveQuests.mockResolvedValue([])
    render(await QuestsPage())
    expect(screen.getByText(/Bibliothèque de quêtes illisible/)).toBeTruthy()
    expect(screen.getByText("Aucune quête active cette semaine.")).toBeTruthy()
  })

  it("état-major : une carte éditable par membre, lue avec la session ; API muette → erreur", async () => {
    api.getStaff.mockResolvedValue({ staff: [{ id: "7", name: "Kéfir", avatar: null, role: "Modo", grade: null, level: null, motto: "Salut", games: [] }] })
    api.getGames.mockResolvedValue({ games: [] })
    render(await StaffPage())
    expect(api.getStaff).toHaveBeenCalledWith("tok")
    expect((screen.getByLabelText("Phrase de Kéfir") as HTMLInputElement).value).toBe("Salut")
    cleanup()
    api.getStaff.mockResolvedValue(null)
    render(await StaffPage())
    expect(screen.getByText(/État-major illisible/)).toBeTruthy()
  })

  it("jeux : jeux désactivés listés ; API muette → erreur", async () => {
    api.getAdminGames.mockResolvedValue([
      { key: "old", name: "Ancien", color: "#000000", image: null, tagline: null, discord_role_id: null, forum_channel_id: null, position: 2, active: false },
      { key: "lol", name: "LoL", color: "#F5A623", image: null, tagline: "Accroche", discord_role_id: null, forum_channel_id: null, position: 1, active: true },
    ])
    render(await GamesPage())
    const items = screen.getAllByRole("listitem")
    expect(within(items[0]).getByText("LoL")).toBeTruthy()
    expect(within(items[1]).getByText("Désactivé")).toBeTruthy()
    cleanup()
    api.getAdminGames.mockResolvedValue(null)
    render(await GamesPage())
    expect(screen.getByText(/Liste des jeux illisible/)).toBeTruthy()
  })

  it("contenus : deux pages Markdown et les grades, lus frais ; échecs signalés page par page", async () => {
    api.getPageFresh.mockImplementation(async (slug: string) =>
      slug === "reglement" ? { slug, title: "Règlement", body_md: "# Règles", updated_at: null } : null,
    )
    api.getGradesFresh.mockResolvedValue([{ name: "Recrue", slug: "recrue", color: "#AAAAAA", level_min: 1 }])
    render(await ContentPage())
    expect(api.getPageFresh).toHaveBeenCalledWith("mentions-legales", "tok")
    expect(screen.getByRole("heading", { level: 2, name: "Règlement" })).toBeTruthy()
    expect(screen.getByText(/Mentions légales illisible/)).toBeTruthy()
    expect(screen.getByRole("form", { name: "Grade Recrue" })).toBeTruthy()
  })
})
