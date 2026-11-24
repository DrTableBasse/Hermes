import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

vi.mock("server-only", () => ({}))
vi.mock("next/headers", () => ({ cookies: async () => ({ get: () => ({ value: "tok" }) }) }))
vi.mock("next/navigation", () => ({ usePathname: () => "/admin/roles" }))
// Suivi des travaux accéléré : quelques millisecondes entre deux relevés.
vi.mock("@/lib/jobs", async orig => ({ ...(await orig<typeof import("@/lib/jobs")>()), JOB_POLL_MS: 5 }))

const server = vi.hoisted(() => ({ getSessionUser: vi.fn(), getAdminRoles: vi.fn() }))
vi.mock("@/lib/api/server", () => server)

const client = vi.hoisted(() => ({
  api: {
    users: { stats: vi.fn() },
    admin: {
      getWarns: vi.fn(),
      roles: vi.fn(),
      createRole: vi.fn(),
      updateRole: vi.fn(),
      deleteRole: vi.fn(),
      bulkRoles: vi.fn(),
      job: vi.fn(),
      addMemberRole: vi.fn(),
      removeMemberRole: vi.fn(),
      memberRoles: vi.fn(),
    },
  },
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

// Recherche de membre simplifiée : chaque clic choisit le membre suivant de la liste.
const picks = vi.hoisted(() => ({
  users: [
    { user_id: "11", username: "Cam", discord_avatar: null },
    { user_id: "12", username: "Lou", discord_avatar: null },
  ],
  next: 0,
}))
vi.mock("@/components/admin/user-search-input", () => ({
  UserSearchInput: ({ label, onSelect }: { label: string; onSelect: (u: unknown) => void }) => (
    <button type="button" onClick={() => onSelect(picks.users[picks.next++ % picks.users.length])}>
      {label}
    </button>
  ),
}))

vi.mock("@/lib/auth-client", () => ({
  authClient: { useSession: { listen: () => () => {}, get: () => null }, signIn: { social: vi.fn() }, signOut: vi.fn() },
}))

import AdminLayout from "@/app/[locale]/admin/layout"
import AdminRolesPage from "@/app/[locale]/admin/roles/page"
import { CONFIRM_GUARD_MS } from "@/components/admin/confirm-button"
import { MemberInspector } from "@/components/admin/member-inspector"
import { allowedSections } from "@/lib/admin-sections"

const role = (id: string, name: string, position: number, members: number, extra: Record<string, unknown> = {}) => ({
  id, name, color: 0x9b59b6, position, managed: false, members, below_bot: true, editable: false, ...extra,
})

const ROLES = {
  roles: [
    role("900", "Chef", 20, 2),
    role("700", "Modérateur", 12, 4),
    role("400", "Fortnite", 6, 37, { editable: true }),
    role("350", "Rédacteur", 5, 12, { editable: true }),
    role("300", "Hermes", 3, 1, { managed: true }),
  ],
  actor: { top_position: 12, is_owner: false, permissions: ["roles.manage", "members.roles"] },
}

const me = (permissions: string[]) => ({ user_id: "1", is_admin: false, is_redacteur: false, permissions })
const row = (name: string) => within(screen.getByRole("row", { name: new RegExp(`^${name}\\b`) }))
const region = (name: string | RegExp) => within(screen.getByRole("region", { name }))

/** Ouvre une confirmation puis la valide au-delà de la garde anti double activation. */
async function confirm(scope: ReturnType<typeof within>, trigger: string, confirmLabel: string) {
  vi.useFakeTimers({ toFake: ["Date"] })
  try {
    fireEvent.click(scope.getByRole("button", { name: trigger }))
    vi.setSystemTime(Date.now() + CONFIRM_GUARD_MS)
    const group = scope.getByRole("group", { name: /\?$/ })
    await act(async () => {
      fireEvent.click(within(group).getByRole("button", { name: confirmLabel }))
    })
    return group
  } finally {
    vi.useRealTimers()
  }
}

beforeEach(() => {
  picks.next = 0
  server.getSessionUser.mockResolvedValue(me(["roles.manage", "members.roles"]))
  server.getAdminRoles.mockResolvedValue(structuredClone(ROLES))
  client.api.admin.roles.mockResolvedValue(structuredClone(ROLES))
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe("sections Rôles et Règles", () => {
  it("roles.manage ouvre « Rôles » et « Règles » ; members.roles seul ouvre « Rôles »", () => {
    expect(allowedSections(["roles.manage"]).map(s => [s.href, s.label])).toEqual([
      ["/admin/roles", "Rôles"],
      ["/admin/regles", "Règles"],
    ])
    expect(allowedSections(["members.roles"]).map(s => s.href)).toEqual(["/admin/roles"])
  })

  it("navigation : liens « Rôles » et « Règles » visibles avec roles.manage seulement", async () => {
    server.getSessionUser.mockResolvedValue(me(["roles.manage"]))
    render(await AdminLayout({ children: <p>contenu</p> }))
    const nav = within(screen.getByRole("navigation", { name: "Administration" }))
    expect(nav.getAllByRole("link").map(a => a.textContent)).toEqual(["Rôles", "Règles"])
    cleanup()
    server.getSessionUser.mockResolvedValue(me(["members.roles"]))
    render(await AdminLayout({ children: <p>contenu</p> }))
    expect(
      within(screen.getByRole("navigation", { name: "Administration" }))
        .getAllByRole("link")
        .map(a => a.textContent),
    ).toEqual(["Rôles"])
    cleanup()
    server.getSessionUser.mockResolvedValue(me(["moderation.view"]))
    render(await AdminLayout({ children: <p>contenu</p> }))
    expect(screen.queryByRole("link", { name: "Rôles" })).toBeNull()
  })
})

describe("page /admin/roles", () => {
  it("sans roles.manage ni members.roles : 403, la liste des rôles n’est pas lue", async () => {
    server.getSessionUser.mockResolvedValue(me(["moderation.view"]))
    render(await AdminRolesPage())
    expect(screen.getByText("Erreur 403")).toBeTruthy()
    expect(screen.getByText(/Gérer les rôles.*ou.*Donner ou retirer des rôles/)).toBeTruthy()
    expect(server.getAdminRoles).not.toHaveBeenCalled()
  })

  it("members.roles seul : rôles et attribution en lot, sans création, modification ni suppression", async () => {
    server.getSessionUser.mockResolvedValue(me(["members.roles"]))
    render(await AdminRolesPage())
    expect(screen.getByRole("table", { name: "Rôles du serveur" })).toBeTruthy()
    expect(screen.getByRole("region", { name: "Attribuer en lot" })).toBeTruthy()
    expect(screen.queryByRole("button", { name: "Nouveau rôle" })).toBeNull()
    expect(screen.queryByRole("button", { name: "Supprimer" })).toBeNull()
    expect(screen.queryByRole("button", { name: /^Modifier/ })).toBeNull()
  })

  it("API muette : message d’erreur, aucun tableau", async () => {
    server.getAdminRoles.mockResolvedValue(null)
    render(await AdminRolesPage())
    expect(screen.getByRole("alert").textContent).toMatch(/illisibles/)
    expect(screen.queryByRole("table")).toBeNull()
  })

  it("tableau : nombre de membres, actions sur les rôles gérables, rôles au-dessus grisés", async () => {
    render(await AdminRolesPage())
    expect(server.getAdminRoles).toHaveBeenCalledWith("tok")
    expect(screen.getByRole("heading", { level: 1, name: "Rôles" })).toBeTruthy()
    const table = within(screen.getByRole("table", { name: "Rôles du serveur" }))
    expect(table.getAllByRole("columnheader").map(h => h.textContent)).toEqual(["Rôle", "Membres", "Actions"])
    expect(row("Fortnite").getByText("37 membres")).toBeTruthy()
    expect(row("Fortnite").getByRole("button", { name: "Modifier « Fortnite »" })).toBeTruthy()
    expect(row("Fortnite").getByRole("button", { name: "Supprimer" })).toBeTruthy()
    expect(row("Chef").getByText("Au-dessus de vous")).toBeTruthy()
    expect(row("Chef").queryAllByRole("button")).toHaveLength(0)
    expect(row("Modérateur").getByText("Votre rôle le plus haut")).toBeTruthy()
    expect(row("Hermes").getByText("Géré par une intégration")).toBeTruthy()
    expect(row("Hermes").getByText("1 membre")).toBeTruthy()
  })

  it("rôle au-dessus du bot : signalé, non modifiable", async () => {
    const data = structuredClone(ROLES)
    data.roles[3] = { ...data.roles[3], below_bot: false, editable: false }
    server.getAdminRoles.mockResolvedValue(data)
    render(await AdminRolesPage())
    expect(row("Rédacteur").getByText("Au-dessus du bot")).toBeTruthy()
    expect(row("Rédacteur").queryAllByRole("button")).toHaveLength(0)
  })

  it("nouveau rôle : POST avec nom et couleur, liste relue, succès annoncé", async () => {
    client.api.admin.createRole.mockResolvedValue({ id: "450", name: "Valorant" })
    render(await AdminRolesPage())
    fireEvent.click(screen.getByRole("button", { name: "Nouveau rôle" }))
    const form = region("Nouveau rôle")
    fireEvent.change(form.getByLabelText("Nom du rôle"), { target: { value: "  Valorant " } })
    fireEvent.change(form.getByLabelText("Couleur"), { target: { value: "#ff4655" } })
    fireEvent.click(form.getByRole("button", { name: "Créer le rôle" }))
    await waitFor(() => expect(screen.getByRole("status", { name: "Rôles" }).textContent).toBe("Rôle « Valorant » créé."))
    expect(client.api.admin.createRole).toHaveBeenCalledWith({ name: "Valorant", color: 0xff4655 })
    expect(client.api.admin.roles).toHaveBeenCalledTimes(1)
  })

  it("nouveau rôle refusé (422) : texte de l’API affiché, formulaire conservé", async () => {
    client.api.admin.createRole.mockRejectedValue(new client.ApiError(422, "String should have at most 100 characters"))
    render(await AdminRolesPage())
    fireEvent.click(screen.getByRole("button", { name: "Nouveau rôle" }))
    const form = region("Nouveau rôle")
    fireEvent.change(form.getByLabelText("Nom du rôle"), { target: { value: "x".repeat(100) } })
    fireEvent.click(form.getByRole("button", { name: "Créer le rôle" }))
    expect((await form.findByRole("alert")).textContent).toMatch(/at most 100 characters/)
    expect((form.getByLabelText("Nom du rôle") as HTMLInputElement).value).toBe("x".repeat(100))
  })

  it("nom vide : rien n’est envoyé, champ signalé", async () => {
    render(await AdminRolesPage())
    fireEvent.click(screen.getByRole("button", { name: "Nouveau rôle" }))
    const form = region("Nouveau rôle")
    fireEvent.change(form.getByLabelText("Nom du rôle"), { target: { value: "   " } })
    fireEvent.click(form.getByRole("button", { name: "Créer le rôle" }))
    expect(form.getByRole("alert").textContent).toBe("Donne un nom au rôle.")
    expect(form.getByLabelText("Nom du rôle").getAttribute("aria-invalid")).toBe("true")
    expect(client.api.admin.createRole).not.toHaveBeenCalled()
  })

  it("modifier : seuls les champs changés partent, liste relue", async () => {
    client.api.admin.updateRole.mockResolvedValue({ id: "400", name: "Fortnite FR" })
    render(await AdminRolesPage())
    fireEvent.click(row("Fortnite").getByRole("button", { name: "Modifier « Fortnite »" }))
    const form = region("Modifier « Fortnite »")
    expect((form.getByLabelText("Couleur") as HTMLInputElement).value).toBe("#9b59b6")
    fireEvent.change(form.getByLabelText("Nom du rôle"), { target: { value: "Fortnite FR" } })
    fireEvent.click(form.getByRole("button", { name: "Enregistrer" }))
    await waitFor(() => expect(screen.getByRole("status", { name: "Rôles" }).textContent).toBe("Rôle « Fortnite FR » enregistré."))
    expect(client.api.admin.updateRole).toHaveBeenCalledWith("400", { name: "Fortnite FR" })
    expect(client.api.admin.roles).toHaveBeenCalledTimes(1)
  })

  it("supprimer : la confirmation annonce le nombre de membres, envoyé à l’API", async () => {
    client.api.admin.deleteRole.mockResolvedValue({ ok: true })
    render(await AdminRolesPage())
    const group = await confirm(row("Fortnite"), "Supprimer", "Supprimer")
    expect(group.getAttribute("aria-label")).toBe("Supprimer « Fortnite » et le retirer à 37 membres ?")
    expect(client.api.admin.deleteRole).toHaveBeenCalledWith("400", 37)
    await waitFor(() => expect(screen.getByRole("status", { name: "Rôles" }).textContent).toBe("Rôle « Fortnite » supprimé."))
    expect(client.api.admin.roles).toHaveBeenCalledTimes(1)
  })

  it("supprimer refusé (409, nombre changé) : texte de l’API en alerte, liste relue", async () => {
    const detail = "Le nombre a changé : ce rôle compte maintenant 38 membre(s), confirmez à nouveau"
    client.api.admin.deleteRole.mockRejectedValue(new client.ApiError(409, detail))
    render(await AdminRolesPage())
    await confirm(row("Fortnite"), "Supprimer", "Supprimer")
    expect((await screen.findByRole("alert")).textContent).toMatch(/ce rôle compte maintenant 38 membre/)
    expect(client.api.admin.roles).toHaveBeenCalledTimes(1)
  })

  it("refus 403 (anti-escalade) : motif de l’API affiché tel quel", async () => {
    const detail = "Ce rôle est au niveau du vôtre ou au-dessus : vous ne pouvez pas le gérer"
    client.api.admin.deleteRole.mockRejectedValue(new client.ApiError(403, detail))
    render(await AdminRolesPage())
    await confirm(row("Rédacteur"), "Supprimer", "Supprimer")
    expect((await screen.findByRole("alert")).textContent).toBe(detail)
  })
})

describe("attribution en lot", () => {
  const bulk = () => region("Attribuer en lot")

  it("sans members.roles : aucune attribution en lot", async () => {
    server.getSessionUser.mockResolvedValue(me(["roles.manage"]))
    render(await AdminRolesPage())
    expect(screen.queryByRole("region", { name: "Attribuer en lot" })).toBeNull()
  })

  it("seuls les rôles gérables sont proposés à l’attribution", async () => {
    render(await AdminRolesPage())
    const options = within(bulk().getByLabelText("Rôle")).getAllByRole("option")
    expect(options.map(o => o.textContent)).toEqual(["Fortnite", "Rédacteur"])
  })

  it("porteurs d’un rôle : nombre annoncé (bots possibles), confirmation, suivi jusqu’à « terminé »", async () => {
    client.api.admin.bulkRoles.mockResolvedValue({ job_id: "j1" })
    client.api.admin.job
      .mockResolvedValueOnce({ state: "running", done: 4, total: 12, errors: 0 })
      .mockResolvedValue({ state: "done", done: 12, total: 12, errors: 1 })
    render(await AdminRolesPage())
    const b = bulk()
    fireEvent.change(b.getByLabelText("Rôle"), { target: { value: "400" } })
    fireEvent.click(b.getByRole("radio", { name: "Tous ceux qui ont le rôle" }))
    fireEvent.change(b.getByLabelText("Rôle source"), { target: { value: "350" } })
    expect(b.getByText("12 membres concernés")).toBeTruthy()
    expect(b.getByText(/peut inclure quelques bots/)).toBeTruthy()
    const group = await confirm(b, "Confirmer", "Confirmer")
    expect(group.getAttribute("aria-label")).toBe("Ajouter « Fortnite » à 12 membres ?")
    expect(client.api.admin.bulkRoles).toHaveBeenCalledWith("400", { action: "add", from_role_id: "350", confirm_count: 12 })
    await waitFor(() => expect(b.getByRole("status", { name: "Suivi du lot" }).textContent).toMatch(/^Terminé/))
    expect(b.getByRole("status", { name: "Suivi du lot" }).textContent).toBe(
      "Terminé : 12 membres traités sur 12, 1 erreur.",
    )
    expect(client.api.admin.job).toHaveBeenCalledWith("j1")
    expect(client.api.admin.job).toHaveBeenCalledTimes(2)
  })

  it("membres choisis : retrait envoyé avec leurs identifiants ; travail perdu (404) → « interrompu »", async () => {
    client.api.admin.bulkRoles.mockResolvedValue({ job_id: "j2" })
    client.api.admin.job.mockRejectedValue(new client.ApiError(404, "Travail inconnu (bot redémarré ou travail expiré)"))
    render(await AdminRolesPage())
    const b = bulk()
    fireEvent.change(b.getByLabelText("Rôle"), { target: { value: "350" } })
    fireEvent.click(b.getByRole("radio", { name: "Retirer" }))
    fireEvent.click(b.getByRole("button", { name: "Ajouter un membre" }))
    fireEvent.click(b.getByRole("button", { name: "Ajouter un membre" }))
    fireEvent.click(b.getByRole("button", { name: "Ajouter un membre" })) // Cam à nouveau : ignoré
    expect(within(b.getByRole("list", { name: "Membres choisis" })).getAllByRole("listitem")).toHaveLength(2)
    expect(b.getByText("2 membres concernés")).toBeTruthy()
    expect(b.queryByText(/peut inclure quelques bots/)).toBeNull()
    fireEvent.click(b.getByRole("button", { name: "Retirer Lou de la liste" }))
    expect(b.getByText("1 membre concerné")).toBeTruthy()
    fireEvent.click(b.getByRole("button", { name: "Ajouter un membre" })) // Lou
    const group = await confirm(b, "Confirmer", "Confirmer")
    expect(group.getAttribute("aria-label")).toBe("Retirer « Rédacteur » à 2 membres ?")
    expect(client.api.admin.bulkRoles).toHaveBeenCalledWith("350", {
      action: "remove",
      user_ids: ["11", "12"],
      confirm_count: 2,
    })
    const alert = await b.findByRole("alert")
    expect(alert.textContent).toMatch(/^Interrompu/)
    expect(alert.textContent).toMatch(/rien n’est repris automatiquement/)
  })

  it("travail interrompu par le bot : nombre traité affiché", async () => {
    client.api.admin.bulkRoles.mockResolvedValue({ job_id: "j3" })
    client.api.admin.job.mockResolvedValue({ state: "interrupted", done: 3, total: 10, errors: 0 })
    render(await AdminRolesPage())
    const b = bulk()
    fireEvent.change(b.getByLabelText("Rôle"), { target: { value: "400" } })
    fireEvent.click(b.getByRole("radio", { name: "Tous ceux qui ont le rôle" }))
    fireEvent.change(b.getByLabelText("Rôle source"), { target: { value: "350" } })
    await confirm(b, "Confirmer", "Confirmer")
    expect((await b.findByRole("alert")).textContent).toBe(
      "Interrompu : 3 membres traités sur 10 avant l’arrêt d’Hermes ; rien n’est repris automatiquement.",
    )
  })

  it("lot refusé (422 > 500 membres) : message de l’API affiché, aucun suivi", async () => {
    client.api.admin.bulkRoles.mockRejectedValue(new client.ApiError(422, "Le rôle source compte plus de 500 membres : lot refusé"))
    render(await AdminRolesPage())
    const b = bulk()
    fireEvent.change(b.getByLabelText("Rôle"), { target: { value: "400" } })
    fireEvent.click(b.getByRole("radio", { name: "Tous ceux qui ont le rôle" }))
    fireEvent.change(b.getByLabelText("Rôle source"), { target: { value: "350" } })
    await confirm(b, "Confirmer", "Confirmer")
    expect((await b.findByRole("alert")).textContent).toMatch(/Le rôle source compte plus de 500 membres : lot refusé/)
    expect(client.api.admin.job).not.toHaveBeenCalled()
  })

  it("aucun membre choisi : « Confirmer » désactivé", async () => {
    render(await AdminRolesPage())
    const b = bulk()
    fireEvent.change(b.getByLabelText("Rôle"), { target: { value: "400" } })
    expect(b.getByText("0 membre concerné")).toBeTruthy()
    expect((b.getByRole("button", { name: "Confirmer" }) as HTMLButtonElement).disabled).toBe(true)
  })
})

describe("fiche d’un membre : rôles", () => {
  const CAM = { user_id: "11", username: "Cam", discord_avatar: null }
  const PROFILE = {
    user: { user_id: "11", username: "Cam", nickname: null, discord_avatar: null, last_seen: null },
    stats: { total_messages: 1, voice_hours: 1, msg_rank: 1, voice_rank: 1, current_level: 1, xp_total: 1 },
    achievements: [],
  }

  beforeEach(() => {
    client.api.users.stats.mockResolvedValue(PROFILE)
    client.api.admin.getWarns.mockResolvedValue({ warns: [] })
  })

  const held = (...roles: Array<[string, string, boolean]>) => ({
    roles: roles.map(([id, name, editable], i) => ({ id, name, color: 0x9b59b6, position: 20 - i, managed: false, editable })),
  })

  it("sans members.roles : rôles portés en lecture seule", async () => {
    client.api.admin.memberRoles.mockResolvedValue(held(["900", "Chef", false], ["400", "Fortnite", false]))
    render(<MemberInspector member={CAM} onMember={vi.fn()} refreshKey={0} />)
    const g = within(await screen.findByRole("group", { name: "Rôles du membre" }))
    const list = within(await g.findByRole("list", { name: "Rôles portés" }))
    expect(list.getAllByRole("listitem").map(li => li.textContent)).toEqual(["Chef", "Fortnite"])
    expect(g.queryByRole("button")).toBeNull()
    expect(g.queryByRole("combobox")).toBeNull()
    expect(client.api.admin.roles).not.toHaveBeenCalled()
  })

  it("rôles portés : « Retirer » sur les seuls gérables, « Donner » propose les gérables non portés", async () => {
    client.api.admin.memberRoles.mockResolvedValue(held(["900", "Chef", false], ["400", "Fortnite", true]))
    client.api.admin.addMemberRole.mockResolvedValue({ ok: true })
    client.api.admin.removeMemberRole.mockResolvedValue({ ok: true })
    render(<MemberInspector member={CAM} onMember={vi.fn()} refreshKey={0} canManageRoles />)
    const g = within(await screen.findByRole("group", { name: "Rôles du membre" }))
    const list = within(await g.findByRole("list", { name: "Rôles portés" }))
    const chef = within(list.getByText("Chef").closest("li") as HTMLElement)
    expect(chef.queryByRole("button")).toBeNull()
    const select = (await g.findByRole("option", { name: "Rédacteur" })).closest("select") as HTMLSelectElement
    expect(within(select).getAllByRole("option").map(o => o.textContent)).toEqual(["Choisir un rôle", "Rédacteur"])

    fireEvent.change(select, { target: { value: "350" } })
    fireEvent.click(g.getByRole("button", { name: "Donner" }))
    await waitFor(() => expect(g.getByRole("status").textContent).toBe("Rôle « Rédacteur » donné à Cam."))
    expect(client.api.admin.addMemberRole).toHaveBeenCalledWith("11", "350")
    expect(client.api.admin.memberRoles).toHaveBeenCalledTimes(2)

    const fortnite = within(within(g.getByRole("list", { name: "Rôles portés" })).getByText("Fortnite").closest("li") as HTMLElement)
    await confirm(fortnite, "Retirer", "Retirer")
    expect(client.api.admin.removeMemberRole).toHaveBeenCalledWith("11", "400")
    await waitFor(() => expect(g.getByRole("status").textContent).toBe("Rôle « Fortnite » retiré à Cam."))
    expect(client.api.admin.memberRoles).toHaveBeenCalledTimes(3)
  })

  it("membre parti du serveur : signalé, rien à donner", async () => {
    client.api.admin.memberRoles.mockRejectedValue(new client.ApiError(404, "Member not found"))
    render(<MemberInspector member={CAM} onMember={vi.fn()} refreshKey={0} canManageRoles />)
    const g = within(await screen.findByRole("group", { name: "Rôles du membre" }))
    expect((await g.findByText("Ce membre n’est plus sur le serveur.")).textContent).toBeTruthy()
    expect(g.queryByRole("button", { name: "Donner" })).toBeNull()
  })

  it("refus de l’API : motif affiché en alerte", async () => {
    client.api.admin.memberRoles.mockResolvedValue(held(["900", "Chef", false]))
    const detail = "Ce rôle n'est pas sous le rôle le plus haut du bot"
    client.api.admin.addMemberRole.mockRejectedValue(new client.ApiError(403, detail))
    render(<MemberInspector member={CAM} onMember={vi.fn()} refreshKey={0} canManageRoles />)
    const g = within(await screen.findByRole("group", { name: "Rôles du membre" }))
    const select = (await g.findByRole("option", { name: "Fortnite" })).closest("select") as HTMLSelectElement
    fireEvent.change(select, { target: { value: "400" } })
    fireEvent.click(g.getByRole("button", { name: "Donner" }))
    expect((await g.findByRole("alert")).textContent).toBe(detail)
  })
})
