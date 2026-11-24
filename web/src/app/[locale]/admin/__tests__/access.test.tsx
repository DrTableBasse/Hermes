import { cleanup, render, screen } from "@testing-library/react"
import type { ReactElement } from "react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { PERMISSIONS } from "@/lib/permissions"

vi.mock("server-only", () => ({}))
vi.mock("next/navigation", () => ({ usePathname: () => "/admin/jeux", useSearchParams: () => new URLSearchParams() }))

const cookieJar = vi.hoisted(() => new Map<string, string>())
vi.mock("next/headers", () => ({
  cookies: async () => ({ get: (name: string) => (cookieJar.has(name) ? { value: cookieJar.get(name) } : undefined) }),
}))

// Toute lecture admin est un espion : un refus ne doit en déclencher aucune.
const api = vi.hoisted(() => {
  const names = [
    "getSessionUser", "getAdminStats", "getAdminCommands", "getAdminSettings", "getDiscordChannels",
    "getDiscordRoles", "getAdminGames", "getAdminGallery", "getQuestTemplates", "getActiveQuests",
    "getAnalytics", "getPageFresh", "getGradesFresh", "getTickets", "getStaff", "getGames", "getAdminAccess",
    "getAdminRoles", "getRoleRules", "getAchievementCatalog",
  ]
  return Object.fromEntries(names.map(n => [n, vi.fn()]))
})
vi.mock("@/lib/api/server", () => api)
vi.mock("@/lib/admin-role", () => ({ readAdminRoleRef: async () => ({ id: "0" }), ADMIN_ROLE_NAME: "Administration" }))

import AdminLayout from "@/app/[locale]/admin/layout"
import AccessPage from "@/app/[locale]/admin/acces/page"
import { ADMIN_SECTIONS, sectionPermissions } from "@/lib/admin-sections"
import AdminHome from "@/app/[locale]/admin/page"
import AnalyticsPage from "@/app/[locale]/admin/analytique/page"
import CommandsPage from "@/app/[locale]/admin/commandes/page"
import ContentPage from "@/app/[locale]/admin/contenus/page"
import StaffPage from "@/app/[locale]/admin/etat-major/page"
import GalleryPage from "@/app/[locale]/admin/galerie/page"
import GamesPage from "@/app/[locale]/admin/jeux/page"
import ModerationPage from "@/app/[locale]/admin/moderation/page"
import QuestsPage from "@/app/[locale]/admin/quetes/page"
import RulesPage from "@/app/[locale]/admin/regles/page"
import SettingsPage from "@/app/[locale]/admin/reglages/page"
import RolesPage from "@/app/[locale]/admin/roles/page"
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
  ["rôles", () => RolesPage()],
  ["règles", () => RulesPage()],
  ["accès", () => AccessPage()],
]

// Correspondance page → droit (celui des routes web-api que la page lit ; tâche 3).
const PAGE_RIGHTS: Array<[string, string, string]> = [
  ["vue d’ensemble", "/admin", "admin.view"],
  ["réglages", "/admin/reglages", "settings.manage"],
  ["modération", "/admin/moderation", "moderation.view"],
  ["commandes", "/admin/commandes", "settings.manage"],
  ["quêtes", "/admin/quetes", "quests.manage"],
  ["tickets", "/admin/tickets", "tickets.manage"],
  ["galerie", "/admin/galerie", "gallery.manage"],
  ["état-major", "/admin/etat-major", "content.edit"],
  ["jeux", "/admin/jeux", "games.manage"],
  ["contenus", "/admin/contenus", "content.edit"],
  ["analytique", "/admin/analytique", "analytics.view"],
  ["rôles", "/admin/roles", "roles.manage"],
  ["règles", "/admin/regles", "roles.manage"],
  ["accès", "/admin/acces", "permissions.manage"],
]
const ALL = Object.keys(PERMISSIONS).sort()
const withRights = (permissions: string[]) => ({ user_id: "100", is_admin: false, is_redacteur: false, permissions })

const member = (is_admin: boolean) => ({
  user_id: "100",
  is_admin,
  is_redacteur: false,
  permissions: is_admin ? Object.keys(PERMISSIONS).sort() : [],
})
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

  it.each(PAGES)("page %s : sans cookie de session, connexion requise sans appel à l’API", async (_name, run) => {
    cookieJar.clear()
    render(await run())
    expect(screen.getByText("Connexion requise")).toBeTruthy()
    expect(screen.queryByText("Erreur 403")).toBeNull()
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
    expect(nav.querySelectorAll("a")).toHaveLength(14)
    expect(screen.getByRole("link", { name: "Jeux" }).getAttribute("aria-current")).toBe("page")
    expect(screen.getByRole("link", { name: "Réglages" }).getAttribute("aria-current")).toBeNull()
  })

  it("chaque page a son droit, identique à celui de sa section dans la navigation", () => {
    expect(PAGE_RIGHTS.map(([name]) => name)).toEqual(PAGES.map(([name]) => name))
    for (const [, href, right] of PAGE_RIGHTS) expect(ADMIN_SECTIONS.find(s => s.href === href)?.permission).toBe(right)
    expect(ADMIN_SECTIONS).toHaveLength(PAGE_RIGHTS.length)
  })

  it.each(PAGE_RIGHTS)("page %s (%s) : ouverte avec le seul droit %s", async (name, _href, right) => {
    api.getSessionUser.mockResolvedValue(withRights([right]))
    render(await PAGES.find(([n]) => n === name)![1]())
    expect(screen.queryByText("Erreur 403")).toBeNull()
  })

  it.each(PAGE_RIGHTS)("page %s (%s) : 403 avec tous les droits sauf %s, aucune lecture admin", async (name, href, right) => {
    // Une section qu'un autre droit ouvre aussi (« Rôles » : members.roles) : on les retire tous.
    const opening: readonly string[] = sectionPermissions(ADMIN_SECTIONS.find(s => s.href === href)!)
    api.getSessionUser.mockResolvedValue(withRights(ALL.filter(p => !opening.includes(p))))
    render(await PAGES.find(([n]) => n === name)![1]())
    expect(screen.getByText("Erreur 403")).toBeTruthy()
    const label = PERMISSIONS[right as keyof typeof PERMISSIONS]
    expect(screen.getByText(text => text.includes(`« ${label} »`))).toBeTruthy()
    expect(adminReads()).toEqual([])
  })
})
