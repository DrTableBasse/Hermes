import { cleanup, render, screen } from "@testing-library/react"
import type { ReactElement } from "react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

vi.mock("server-only", () => ({}))
vi.mock("next/navigation", () => ({ usePathname: () => "/admin/jeux" }))

const cookieJar = vi.hoisted(() => new Map<string, string>())
vi.mock("next/headers", () => ({
  cookies: async () => ({ get: (name: string) => (cookieJar.has(name) ? { value: cookieJar.get(name) } : undefined) }),
}))

// Toute lecture admin est un espion : un refus ne doit en déclencher aucune.
const api = vi.hoisted(() => {
  const names = [
    "getSessionUser", "getAdminStats", "getAdminCommands", "getAdminSettings", "getDiscordChannels",
    "getDiscordRoles", "getAdminGames", "getAdminGallery", "getQuestTemplates", "getActiveQuests",
    "getAnalytics", "getPageFresh", "getGradesFresh", "getTickets", "getStaff", "getGames",
  ]
  return Object.fromEntries(names.map(n => [n, vi.fn()]))
})
vi.mock("@/lib/api/server", () => api)

import AdminLayout from "@/app/[locale]/admin/layout"
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

const PAGES: Array<[string, () => Promise<ReactElement>]> = [
  ["vue d’ensemble", () => AdminHome()],
  ["réglages", () => SettingsPage()],
  ["modération", () => ModerationPage()],
  ["commandes", () => CommandsPage()],
  ["quêtes", () => QuestsPage()],
  ["tickets", () => TicketsPage({ searchParams: Promise.resolve({}) })],
  ["galerie", () => GalleryPage()],
  ["état-major", () => StaffPage()],
  ["jeux", () => GamesPage()],
  ["contenus", () => ContentPage()],
  ["analytique", () => AnalyticsPage()],
]

const member = (is_admin: boolean) => ({ user_id: "100", is_admin, is_redacteur: false })
const adminReads = () => Object.entries(api).filter(([n, fn]) => n !== "getSessionUser" && fn.mock.calls.length > 0)

beforeEach(() => {
  cookieJar.set("better-auth.session_token", "tok")
  for (const fn of Object.values(api)) fn.mockResolvedValue(null)
})

afterEach(() => {
  cleanup()
  cookieJar.clear()
  vi.clearAllMocks()
})

describe("accès à /admin", () => {
  it("membre connecté sans isAdmin : page 403 propre dans le layout, enfants jamais rendus", async () => {
    api.getSessionUser.mockResolvedValue(member(false))
    render(await AdminLayout({ children: <p>secret</p> }))
    expect(screen.getByText("Erreur 403")).toBeTruthy()
    expect(screen.getByRole("heading", { level: 1, name: /réservée à l’administration/ })).toBeTruthy()
    expect(screen.queryByText("secret")).toBeNull()
    expect(screen.queryByRole("navigation", { name: "Administration" })).toBeNull()
    expect(api.getSessionUser).toHaveBeenCalledWith("tok")
  })

  it.each(PAGES)("page %s : 403 pour un non-admin, aucune lecture admin", async (_name, run) => {
    api.getSessionUser.mockResolvedValue(member(false))
    render(await run())
    expect(screen.getByText("Erreur 403")).toBeTruthy()
    expect(adminReads()).toEqual([])
  })

  it.each(PAGES)("page %s : sans cookie de session, 403 sans appel à l’API", async (_name, run) => {
    cookieJar.clear()
    render(await run())
    expect(screen.getByText("Erreur 403")).toBeTruthy()
    expect(api.getSessionUser).not.toHaveBeenCalled()
  })

  it("session illisible (API muette) : « vérification impossible », pas un faux 403", async () => {
    api.getSessionUser.mockResolvedValue(null)
    render(await AdminLayout({ children: <p>secret</p> }))
    expect(screen.getByText("Vérification impossible")).toBeTruthy()
    expect(screen.queryByText("Erreur 403")).toBeNull()
    expect(screen.queryByText("secret")).toBeNull()
  })

  it("administrateur : sous-navigation et contenu ; page courante marquée", async () => {
    api.getSessionUser.mockResolvedValue(member(true))
    render(await AdminLayout({ children: <p>contenu</p> }))
    expect(screen.getByText("contenu")).toBeTruthy()
    const nav = screen.getByRole("navigation", { name: "Administration" })
    expect(nav.querySelectorAll("a")).toHaveLength(11)
    expect(screen.getByRole("link", { name: "Jeux" }).getAttribute("aria-current")).toBe("page")
    expect(screen.getByRole("link", { name: "Réglages" }).getAttribute("aria-current")).toBeNull()
  })
})
