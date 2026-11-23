import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

vi.mock("server-only", () => ({}))
vi.mock("next/headers", () => ({ cookies: async () => ({ get: () => ({ value: "tok" }) }) }))
vi.mock("next/navigation", () => ({ usePathname: () => "/admin/moderation" }))

const server = vi.hoisted(() => ({ getSessionUser: vi.fn(), getAdminAccess: vi.fn() }))
vi.mock("@/lib/api/server", () => server)

const auth = vi.hoisted(() => ({ readAdminRoleRef: vi.fn(), ADMIN_ROLE_NAME: "Administration" }))
vi.mock("@/lib/admin-role", () => auth)

const client = vi.hoisted(() => ({
  api: { admin: { putAccess: vi.fn() } },
  ApiError: class ApiError extends Error {
    constructor(
      readonly status: number,
      message: string,
    ) {
      super(message)
    }
  },
}))
vi.mock("@/lib/api/client", () => client)

// Instantané stable (useSyncExternalStore exige la même référence d’un appel à l’autre).
const session = vi.hoisted(() => ({ state: null as { data: { user: Record<string, unknown> } } | null }))
vi.mock("@/lib/auth-client", () => ({
  authClient: {
    useSession: { listen: () => () => {}, get: () => session.state },
    signIn: { social: vi.fn() },
    signOut: vi.fn(),
  },
}))
vi.mock("@/components/account/notification-bell", () => ({ NotificationBell: () => null }))

import AdminLayout from "@/app/[locale]/admin/layout"
import AdminAccessPage from "@/app/[locale]/admin/acces/page"
import { Navbar } from "@/components/layout/navbar"

const role = (id: string, name: string, position: number, extra: Record<string, unknown> = {}) => ({
  id, name, color: 0x9b59b6, position, managed: false, permissions: [] as string[], editable: false, ...extra,
})

const ACCESS = {
  catalog: [],
  roles: [
    role("900", "GroFlex", 20, { permissions: ["moderation.view"] }),
    role("800", "Chef", 15),
    role("700", "Modérateur", 12, { permissions: ["moderation.view", "permissions.manage"] }),
    role("400", "Rédacteur", 5, { permissions: ["articles.write"], editable: true }),
    role("300", "Hermes", 3, { managed: true, editable: true }),
  ],
  actor: {
    top_position: 12,
    is_owner: false,
    permissions: ["articles.publish", "articles.write", "moderation.view", "permissions.manage"],
  },
}

const me = (permissions: string[]) => ({ user_id: "1", is_admin: false, is_redacteur: false, permissions })
const region = (name: string) => within(screen.getByRole("region", { name }))

beforeEach(() => {
  server.getSessionUser.mockResolvedValue(me(["permissions.manage", "moderation.view"]))
  server.getAdminAccess.mockResolvedValue(structuredClone(ACCESS))
  auth.readAdminRoleRef.mockResolvedValue({ id: "900" })
})

afterEach(() => {
  cleanup()
  session.state = null
  vi.clearAllMocks()
})

describe("page /admin/acces", () => {
  it("sans permissions.manage : 403, l’API d’accès n’est pas lue", async () => {
    server.getSessionUser.mockResolvedValue(me(["moderation.view", "settings.manage"]))
    render(await AdminAccessPage())
    expect(screen.getByText("Erreur 403")).toBeTruthy()
    expect(screen.getByText(/Gérer les accès/)).toBeTruthy()
    expect(server.getAdminAccess).not.toHaveBeenCalled()
  })

  it("API muette : message d’erreur, aucune grille", async () => {
    server.getAdminAccess.mockResolvedValue(null)
    render(await AdminAccessPage())
    expect(screen.getByRole("alert").textContent).toMatch(/illisibles/)
    expect(screen.queryAllByRole("checkbox")).toHaveLength(0)
  })

  it("en-tête : rôle et position de l’acteur, rappel du délai d’effet", async () => {
    render(await AdminAccessPage())
    expect(server.getAdminAccess).toHaveBeenCalledWith("tok")
    expect(screen.getByRole("heading", { level: 1, name: "Accès" })).toBeTruthy()
    expect(screen.getByText("vous : Modérateur, position 12")).toBeTruthy()
    expect(screen.getByText(/sous 10 minutes/)).toBeTruthy()
  })

  it("rôle administrateur (réglage admin_role) : « Tous les droits », aucune case", async () => {
    render(await AdminAccessPage())
    const admin = region("GroFlex")
    expect(admin.getByText("Tous les droits (rôle administrateur)")).toBeTruthy()
    expect(admin.queryAllByRole("checkbox")).toHaveLength(0)
    expect(admin.queryByRole("button", { name: /Enregistrer/ })).toBeNull()
  })

  it("rôle admin désigné par son nom (repli de l’environnement) : reconnu aussi", async () => {
    auth.readAdminRoleRef.mockResolvedValue({ name: "GroFlex" })
    render(await AdminAccessPage())
    expect(region("GroFlex").getByText("Tous les droits (rôle administrateur)")).toBeTruthy()
  })

  it("réglage illisible : repli sur le nom de l’environnement (« Administration »)", async () => {
    auth.readAdminRoleRef.mockResolvedValue(null)
    const data = structuredClone(ACCESS)
    data.roles[0].name = "Administration"
    server.getAdminAccess.mockResolvedValue(data)
    render(await AdminAccessPage())
    expect(region("Administration").getByText("Tous les droits (rôle administrateur)")).toBeTruthy()
  })

  it("rôle au-dessus ou au niveau de l’acteur : grisé, non modifiable", async () => {
    render(await AdminAccessPage())
    expect(region("Chef").getByText("Au-dessus de votre rôle")).toBeTruthy()
    expect(region("Chef").queryAllByRole("checkbox")).toHaveLength(0)
    expect(region("Modérateur").getByText("Votre rôle le plus haut : non modifiable")).toBeTruthy()
    expect(region("Modérateur").queryAllByRole("checkbox")).toHaveLength(0)
  })

  it("rôle géré par une intégration : grisé même s’il est sous l’acteur", async () => {
    render(await AdminAccessPage())
    const bot = region("Hermes")
    expect(bot.getByText(/géré par une intégration/)).toBeTruthy()
    expect(bot.queryAllByRole("checkbox")).toHaveLength(0)
  })

  it("rôle éditable : cases groupées, droit non possédé désactivé, droit stocké coché", async () => {
    render(await AdminAccessPage())
    const r = region("Rédacteur")
    for (const g of ["Modération", "Contenu", "Serveur", "Administration"]) expect(r.getByRole("group", { name: g })).toBeTruthy()
    expect(r.getAllByRole("checkbox")).toHaveLength(17)
    const write = r.getByRole("checkbox", { name: "Écrire des articles" }) as HTMLInputElement
    expect(write.checked).toBe(true)
    expect(write.disabled).toBe(false)
    const settings = r.getByRole("checkbox", { name: "Modifier les réglages et les commandes" }) as HTMLInputElement
    expect(settings.disabled).toBe(true)
    expect(settings.checked).toBe(false)
    expect((r.getByRole("checkbox", { name: "Voir la modération et le journal" }) as HTMLInputElement).disabled).toBe(false)
    expect((r.getByRole("button", { name: "Enregistrer" }) as HTMLButtonElement).disabled).toBe(true) // rien de changé
  })

  it("propriétaire : toutes les cases actives", async () => {
    server.getAdminAccess.mockResolvedValue({
      ...structuredClone(ACCESS),
      roles: ACCESS.roles.map(r => ({ ...r, editable: true })),
      actor: { top_position: 99, is_owner: true, permissions: [] },
    })
    render(await AdminAccessPage())
    expect(screen.getByText("vous : propriétaire du serveur")).toBeTruthy()
    const boxes = region("Chef").getAllByRole("checkbox") as HTMLInputElement[]
    expect(boxes.every(b => !b.disabled)).toBe(true)
  })

  it("enregistrer : PUT avec la liste cochée, message de succès annoncé", async () => {
    client.api.admin.putAccess.mockResolvedValue({ id: "400", permissions: ["articles.publish", "articles.write"] })
    render(await AdminAccessPage())
    const r = region("Rédacteur")
    fireEvent.click(r.getByRole("checkbox", { name: "Publier et gérer les étiquettes" }))
    fireEvent.click(r.getByRole("button", { name: "Enregistrer" }))
    expect(client.api.admin.putAccess).toHaveBeenCalledWith("400", ["articles.publish", "articles.write"])
    const status = r.getByRole("status")
    expect(status.textContent).toBe("") // zone d'annonce présente d'emblée, vide avant l'enregistrement
    await waitFor(() => expect(status.textContent).toMatch(/enregistrés/))
    expect(status.textContent).toMatch(/10 minutes/)
    expect((r.getByRole("button", { name: "Enregistrer" }) as HTMLButtonElement).disabled).toBe(true)
  })

  it("décocher puis enregistrer : le droit retiré n’est plus envoyé", async () => {
    client.api.admin.putAccess.mockResolvedValue({ id: "400", permissions: [] })
    render(await AdminAccessPage())
    const r = region("Rédacteur")
    fireEvent.click(r.getByRole("checkbox", { name: "Écrire des articles" }))
    fireEvent.click(r.getByRole("button", { name: "Enregistrer" }))
    expect(client.api.admin.putAccess).toHaveBeenCalledWith("400", [])
    await waitFor(() => expect(r.getByRole("status").textContent).toMatch(/enregistrés/))
  })

  it("refus 403 de l’API : texte de l’erreur affiché en alerte, cases conservées", async () => {
    const detail = "Vous ne pouvez accorder ou retirer que des droits que vous possédez : settings.manage"
    client.api.admin.putAccess.mockRejectedValue(new client.ApiError(403, detail))
    render(await AdminAccessPage())
    const r = region("Rédacteur")
    fireEvent.click(r.getByRole("checkbox", { name: "Publier et gérer les étiquettes" }))
    fireEvent.click(r.getByRole("button", { name: "Enregistrer" }))
    expect((await r.findByRole("alert")).textContent).toBe(detail)
    expect(r.getByRole("status").textContent).toBe("")
    expect((r.getByRole("checkbox", { name: "Publier et gérer les étiquettes" }) as HTMLInputElement).checked).toBe(true)
  })
})

describe("navigation filtrée par droit", () => {
  it("cadre /admin : la navigation ne liste que les sections autorisées", async () => {
    server.getSessionUser.mockResolvedValue(me(["moderation.view", "tickets.manage", "articles.write"]))
    render(await AdminLayout({ children: <p>contenu</p> }))
    const links = within(screen.getByRole("navigation", { name: "Administration" })).getAllByRole("link")
    expect(links.map(a => a.textContent)).toEqual(["Modération", "Tickets"])
    expect(screen.getByRole("link", { name: "Modération" }).getAttribute("aria-current")).toBe("page")
  })

  it("cadre /admin : droits d’articles seuls → 403", async () => {
    server.getSessionUser.mockResolvedValue(me(["articles.write", "articles.publish"]))
    render(await AdminLayout({ children: <p>secret</p> }))
    expect(screen.getByText("Erreur 403")).toBeTruthy()
    expect(screen.queryByText("secret")).toBeNull()
  })

  const openAccountMenu = () => fireEvent.click(screen.getByRole("button", { name: /Sam/ }))

  it("menu : pas d’« Admin » ni d’« Écrire un article » pour un membre sans droit", () => {
    session.state = { data: { user: { name: "Sam", sitePermissions: [] } } }
    render(<Navbar inviteUrl={null} />)
    openAccountMenu()
    expect(screen.getByRole("link", { name: "Profil" })).toBeTruthy()
    expect(screen.queryByRole("link", { name: "Admin" })).toBeNull()
    expect(screen.queryByRole("link", { name: "Écrire un article" })).toBeNull()
  })

  it("menu : « Admin » vers la première section ouverte dès un droit d’admin", () => {
    session.state = { data: { user: { name: "Sam", sitePermissions: ["tickets.manage"] } } }
    render(<Navbar inviteUrl={null} />)
    openAccountMenu()
    expect(screen.getByRole("link", { name: "Admin" }).getAttribute("href")).toBe("/admin/tickets")
    expect(screen.queryByRole("link", { name: "Écrire un article" })).toBeNull()
  })

  it("menu : « Écrire un article » avec articles.write, sans « Admin »", () => {
    session.state = { data: { user: { name: "Sam", sitePermissions: ["articles.write"] } } }
    render(<Navbar inviteUrl={null} />)
    openAccountMenu()
    expect(screen.getByRole("link", { name: "Écrire un article" })).toBeTruthy()
    expect(screen.queryByRole("link", { name: "Admin" })).toBeNull()
  })

  it("menu : session antérieure sans sitePermissions mais isAdmin → « Admin » vers la vue d’ensemble", () => {
    session.state = { data: { user: { name: "Sam", isAdmin: true } } }
    render(<Navbar inviteUrl={null} />)
    openAccountMenu()
    expect(screen.getByRole("link", { name: "Admin" }).getAttribute("href")).toBe("/admin")
  })
})
