import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

vi.mock("server-only", () => ({}))
vi.mock("next/headers", () => ({ cookies: async () => ({ get: () => ({ value: "tok" }) }) }))
vi.mock("next/navigation", () => ({ usePathname: () => "/admin/regles" }))
vi.mock("@/lib/jobs", async orig => ({ ...(await orig<typeof import("@/lib/jobs")>()), JOB_POLL_MS: 5 }))

const server = vi.hoisted(() => ({
  getSessionUser: vi.fn(),
  getAdminRoles: vi.fn(),
  getRoleRules: vi.fn(),
  getAchievementCatalog: vi.fn(),
  getGradesFresh: vi.fn(),
}))
vi.mock("@/lib/api/server", () => server)

const client = vi.hoisted(() => ({
  api: {
    admin: {
      createRoleRule: vi.fn(),
      updateRoleRule: vi.fn(),
      deleteRoleRule: vi.fn(),
      previewRoleRule: vi.fn(),
      applyRoleRule: vi.fn(),
      job: vi.fn(),
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

import AdminRulesPage from "@/app/[locale]/admin/regles/page"
import { CONFIRM_GUARD_MS } from "@/components/admin/confirm-button"

const role = (id: string, name: string, position: number, members: number, editable = true) => ({
  id, name, color: 0, position, managed: false, members, below_bot: true, editable,
})

const ROLES = {
  roles: [role("900", "Chef", 20, 2, false), role("500", "🦇 Batman", 8, 7), role("400", "Fortnite", 6, 37)],
  actor: { top_position: 12, is_owner: false, permissions: ["roles.manage", "members.roles"] },
}

const rule = (id: number, extra: Record<string, unknown>) => ({
  id,
  condition_type: "voice_hours",
  condition_value: "100",
  role_id: null,
  previous_role_id: null,
  create_role_name: null,
  create_role_color: null,
  remove_when_lost: false,
  exclusive_group: null,
  active: true,
  reconcile: false,
  role_name: null,
  missing_role: false,
  achievement_name: null,
  ...extra,
})

const BATMAN = rule(1, { role_id: "500", role_name: "🦇 Batman" })
const RULES = [
  BATMAN,
  rule(2, {
    condition_type: "achievement",
    condition_value: "3",
    create_role_name: "💬 Moulin à paroles",
    create_role_color: 0x95a5a6,
    achievement_name: "Moulin à paroles",
  }),
  rule(3, { condition_type: "level", condition_value: "10", role_id: "999", missing_role: true, active: false }),
]

const CATALOG = {
  achievements: [{ id: 3, name: "Moulin à paroles", description: null, icon: "💬", points: 10, condition_type: "messages", unlocked_count: 4 }],
  members_total: 50,
}
const GRADES = [{ name: "Saucisson", slug: "saucisson", color: "#fff", level_min: 5 }]

const me = (permissions: string[]) => ({ user_id: "1", is_admin: false, is_redacteur: false, permissions })
const row = (text: string) => within(screen.getByRole("row", { name: new RegExp(`^${text}`) }))
const region = (name: string | RegExp) => within(screen.getByRole("region", { name }))

async function confirm(scope: ReturnType<typeof within>, trigger: string, confirmLabel: string) {
  vi.useFakeTimers({ toFake: ["Date"] })
  try {
    fireEvent.click(scope.getByRole("button", { name: trigger }))
    vi.setSystemTime(Date.now() + CONFIRM_GUARD_MS)
    const group = screen.getByRole("group", { name: /\?$/ })
    await act(async () => {
      fireEvent.click(within(group).getByRole("button", { name: confirmLabel }))
    })
    return group
  } finally {
    vi.useRealTimers()
  }
}

/** « Voir l'aperçu » d'une ligne puis attente du panneau d'aperçu. */
async function preview(text: string) {
  fireEvent.click(row(text).getByRole("button", { name: "Voir l’aperçu" }))
  return within(await screen.findByRole("region", { name: /^Aperçu/ }))
}

beforeEach(() => {
  server.getSessionUser.mockResolvedValue(me(["roles.manage", "members.roles"]))
  server.getAdminRoles.mockResolvedValue(structuredClone(ROLES))
  server.getRoleRules.mockResolvedValue(structuredClone(RULES))
  server.getAchievementCatalog.mockResolvedValue(structuredClone(CATALOG))
  server.getGradesFresh.mockResolvedValue(structuredClone(GRADES))
  client.api.admin.previewRoleRule.mockResolvedValue({ gain: [{ id: "11", name: "Cam" }], lose: [], missing_role: false })
  client.api.admin.applyRoleRule.mockResolvedValue({ job_id: "a1", remove_job_id: null })
  client.api.admin.job.mockResolvedValue({
    state: "done", done: 1, total: 1, errors: 0, added: 1, removed: 0, skipped: 0, missing_role: false,
  })
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe("page /admin/regles", () => {
  it("sans roles.manage : 403, aucune lecture", async () => {
    server.getSessionUser.mockResolvedValue(me(["members.roles"]))
    render(await AdminRulesPage())
    expect(screen.getByText("Erreur 403")).toBeTruthy()
    expect(server.getRoleRules).not.toHaveBeenCalled()
  })

  it("API muette : message d’erreur, aucun tableau", async () => {
    server.getRoleRules.mockResolvedValue(null)
    render(await AdminRulesPage())
    expect(screen.getByRole("alert").textContent).toMatch(/illisibles/)
    expect(screen.queryByRole("table")).toBeNull()
  })

  it("tableau : condition, rôle donné, retrait, mode, actif ; rôle introuvable signalé", async () => {
    render(await AdminRulesPage())
    expect(server.getRoleRules).toHaveBeenCalledWith("tok")
    expect(screen.getByRole("heading", { level: 1, name: "Règles automatiques" })).toBeTruthy()
    const table = within(screen.getByRole("table", { name: "Règles automatiques" }))
    expect(table.getAllByRole("columnheader").map(h => h.textContent)).toEqual([
      "Condition", "Rôle donné", "Retiré si perdu", "Mode", "Actif", "Actions",
    ])
    const cells = (text: string) => row(text).getAllByRole("cell").slice(0, 5).map(c => c.textContent)
    expect(cells("Vocal total ≥ 100 h")).toEqual(["Vocal total ≥ 100 h", "🦇 Batman", "non", "Aperçu", "oui"])
    expect(cells("Succès « Moulin à paroles »")).toEqual(["Succès « Moulin à paroles »", "créé au déblocage (💬 Moulin à paroles)", "non", "Aperçu", "oui"])
    expect(cells("Niveau XP ≥ 10")).toEqual(["Niveau XP ≥ 10", "rôle introuvable", "non", "Aperçu", "non"])
    expect(row("Niveau XP ≥ 10").getByText("rôle introuvable").className).toMatch(/text-orange/)
  })

  it("« Valider » reste désactivé tant que l’aperçu n’a pas été vu", async () => {
    render(await AdminRulesPage())
    expect((row("Vocal total").getByRole("button", { name: "Valider" }) as HTMLButtonElement).disabled).toBe(true)
  })

  it("aperçu puis validation : qui gagne / qui perd, application suivie, mode « Appliquée »", async () => {
    client.api.admin.previewRoleRule.mockResolvedValue({
      gain: [{ id: "11", name: "Cam" }, { id: "12", name: "Lou" }],
      lose: [{ id: "13", name: "Max" }],
      missing_role: false,
    })
    client.api.admin.updateRoleRule.mockResolvedValue({ rule: { ...BATMAN, reconcile: true }, previous_role: null, reloaded: true })
    render(await AdminRulesPage())
    const p = await preview("Vocal total")
    expect(client.api.admin.previewRoleRule).toHaveBeenCalledWith(1)
    expect(within(p.getByRole("list", { name: "Gagnent le rôle (2)" })).getAllByRole("listitem").map(li => li.textContent)).toEqual(["Cam", "Lou"])
    expect(within(p.getByRole("list", { name: "Perdent le rôle (1)" })).getAllByRole("listitem").map(li => li.textContent)).toEqual(["Max"])
    const group = await confirm(row("Vocal total"), "Valider", "Appliquer")
    expect(group.getAttribute("aria-label")).toBe("Appliquer « Vocal total ≥ 100 h » : 2 membres gagnent le rôle, 1 le perd ?")
    expect(client.api.admin.applyRoleRule).toHaveBeenCalledWith(1, { confirm: true })
    await waitFor(() => expect(client.api.admin.updateRoleRule).toHaveBeenCalledWith(1, { reconcile: true, preview_seen: true }))
    await waitFor(() =>
      expect(p.getByRole("status", { name: "Application de la règle" }).textContent).toBe(
        "Terminé : 1 ajouté, 0 retiré, 0 déjà pourvu, 0 erreur.",
      ),
    )
    expect(row("Vocal total").getAllByRole("cell")[3].textContent).toBe("Appliquée")
  })

  it("aperçu d’une règle au rôle introuvable : alerte, validation impossible", async () => {
    client.api.admin.previewRoleRule.mockResolvedValue({ gain: [], lose: [], missing_role: true })
    render(await AdminRulesPage())
    const p = await preview("Niveau XP")
    expect(p.getByRole("alert").textContent).toMatch(/rôle introuvable/)
    expect((row("Niveau XP").getByRole("button", { name: "Valider" }) as HTMLButtonElement).disabled).toBe(true)
  })

  it("application refusée (403) : motif de l’API, règle toujours en aperçu", async () => {
    const detail = "Ce rôle est au niveau du vôtre ou au-dessus : vous ne pouvez pas le gérer"
    client.api.admin.applyRoleRule.mockRejectedValue(new client.ApiError(403, detail))
    render(await AdminRulesPage())
    const p = await preview("Vocal total")
    await confirm(row("Vocal total"), "Valider", "Appliquer")
    expect((await p.findByRole("alert")).textContent).toBe(detail)
    expect(client.api.admin.updateRoleRule).not.toHaveBeenCalled()
    expect(row("Vocal total").getAllByRole("cell")[3].textContent).toBe("Aperçu")
  })

  it("nouvelle règle : envoyée en mode aperçu, ajoutée au tableau ; rechargement manqué signalé", async () => {
    client.api.admin.createRoleRule.mockResolvedValue({
      rule: rule(4, { condition_type: "messages", condition_value: "1000", role_id: "400", role_name: "Fortnite" }),
      reloaded: false,
    })
    render(await AdminRulesPage())
    fireEvent.click(screen.getByRole("button", { name: "Nouvelle règle" }))
    const form = region("Nouvelle règle")
    fireEvent.change(form.getByLabelText("Condition"), { target: { value: "messages" } })
    fireEvent.change(form.getByLabelText("Valeur"), { target: { value: "1000" } })
    expect(within(form.getByLabelText("Rôle")).getAllByRole("option").map(o => o.textContent)).toEqual([
      "Choisir un rôle", "🦇 Batman", "Fortnite",
    ])
    fireEvent.change(form.getByLabelText("Rôle"), { target: { value: "400" } })
    fireEvent.click(form.getByRole("button", { name: "Créer la règle" }))
    await waitFor(() => expect(screen.getByRole("row", { name: /^Messages total ≥ 1000/ })).toBeTruthy())
    expect(client.api.admin.createRoleRule).toHaveBeenCalledWith({
      condition_type: "messages",
      condition_value: "1000",
      role_id: "400",
      remove_when_lost: false,
      active: true,
    })
    expect(row("Messages total ≥ 1000").getAllByRole("cell")[3].textContent).toBe("Aperçu")
    expect(screen.getByRole("status", { name: "Règles" }).textContent).toMatch(/redémarrage/)
  })

  it("nouvelle règle de succès « créer au premier déblocage » : succès choisi dans la liste", async () => {
    client.api.admin.createRoleRule.mockResolvedValue({ rule: rule(5, { condition_type: "achievement" }), reloaded: true })
    render(await AdminRulesPage())
    fireEvent.click(screen.getByRole("button", { name: "Nouvelle règle" }))
    const form = region("Nouvelle règle")
    expect(form.queryByRole("radio", { name: "Créer au premier déblocage" })).toBeNull() // succès seulement
    fireEvent.change(form.getByLabelText("Condition"), { target: { value: "achievement" } })
    fireEvent.change(form.getByLabelText("Valeur"), { target: { value: "3" } })
    fireEvent.click(form.getByRole("radio", { name: "Créer au premier déblocage" }))
    fireEvent.change(form.getByLabelText("Nom du rôle à créer"), { target: { value: "💬 Bavard" } })
    fireEvent.change(form.getByLabelText("Groupe exclusif (facultatif)"), { target: { value: " bavards " } })
    fireEvent.click(form.getByRole("button", { name: "Créer la règle" }))
    await waitFor(() => expect(client.api.admin.createRoleRule).toHaveBeenCalled())
    expect(client.api.admin.createRoleRule).toHaveBeenCalledWith({
      condition_type: "achievement",
      condition_value: "3",
      create_role_name: "💬 Bavard",
      create_role_color: 0,
      remove_when_lost: false,
      exclusive_group: "bavards",
      active: true,
    })
  })

  it("création refusée (422 conflit) : texte de l’API affiché", async () => {
    const detail = "Le rôle « Fortnite » est visé par 2 règles actives dont l'une le retire à la perte de la condition : elles se contrediraient."
    client.api.admin.createRoleRule.mockRejectedValue(new client.ApiError(422, detail))
    render(await AdminRulesPage())
    fireEvent.click(screen.getByRole("button", { name: "Nouvelle règle" }))
    const form = region("Nouvelle règle")
    fireEvent.change(form.getByLabelText("Valeur"), { target: { value: "5" } })
    fireEvent.change(form.getByLabelText("Rôle"), { target: { value: "400" } })
    fireEvent.click(form.getByLabelText("Retirer le rôle si la condition est perdue"))
    fireEvent.click(form.getByRole("button", { name: "Créer la règle" }))
    expect((await form.findByRole("alert")).textContent).toMatch(/elles se contrediraient/)
  })

  it("changer le rôle d’une règle : case « retirer l’ancien rôle aux N membres », confirmée par le nombre", async () => {
    client.api.admin.updateRoleRule.mockResolvedValueOnce({
      rule: { ...BATMAN, role_id: "400", role_name: "Fortnite", previous_role_id: "500" },
      previous_role: { id: "500", name: "🦇 Batman", members: 9 },
      reloaded: true,
    })
    client.api.admin.updateRoleRule.mockResolvedValue({
      rule: { ...BATMAN, role_id: "400", role_name: "Fortnite", previous_role_id: "500", reconcile: true },
      previous_role: null,
      reloaded: true,
    })
    client.api.admin.applyRoleRule.mockResolvedValue({ job_id: "a1", remove_job_id: "r1" })
    client.api.admin.job.mockImplementation(async (id: string) =>
      id === "r1"
        ? { state: "done", done: 9, total: 9, errors: 0 }
        : { state: "done", done: 1, total: 1, errors: 0, added: 1, removed: 0, skipped: 0, missing_role: false },
    )
    render(await AdminRulesPage())
    fireEvent.click(row("Vocal total").getByRole("button", { name: "Modifier" }))
    const form = region("Modifier la règle « Vocal total ≥ 100 h »")
    expect((form.getByLabelText("Rôle") as HTMLSelectElement).value).toBe("500")
    fireEvent.change(form.getByLabelText("Rôle"), { target: { value: "400" } })
    fireEvent.click(form.getByRole("button", { name: "Enregistrer" }))
    await waitFor(() => expect(row("Vocal total").getAllByRole("cell")[1].textContent).toBe("Fortnite"))
    expect(client.api.admin.updateRoleRule).toHaveBeenCalledWith(1, { role_id: "400" })

    const p = await preview("Vocal total")
    const box = p.getByRole("checkbox", { name: "Retirer l’ancien rôle « 🦇 Batman » à ses 9 membres" }) as HTMLInputElement
    expect(box.checked).toBe(false)
    fireEvent.click(box)
    const group = await confirm(row("Vocal total"), "Valider", "Appliquer")
    expect(group.getAttribute("aria-label")).toBe(
      "Appliquer « Vocal total ≥ 100 h » : 1 membre gagne le rôle, 0 le perd, et retirer « 🦇 Batman » à 9 membres ?",
    )
    expect(client.api.admin.applyRoleRule).toHaveBeenCalledWith(1, {
      confirm: true,
      remove_previous_role_id: "500",
      confirm_previous_members: 9,
    })
    await waitFor(() =>
      expect(p.getByRole("status", { name: "Retrait de l’ancien rôle" }).textContent).toBe(
        "Terminé : 9 membres traités sur 9, 0 erreur.",
      ),
    )
  })

  it("sans la case : l’ancien rôle n’est pas retiré", async () => {
    server.getRoleRules.mockResolvedValue([{ ...BATMAN, role_id: "400", role_name: "Fortnite", previous_role_id: "500" }])
    client.api.admin.updateRoleRule.mockResolvedValue({ rule: { ...BATMAN, reconcile: true }, previous_role: null, reloaded: true })
    render(await AdminRulesPage())
    const p = await preview("Vocal total")
    // Nombre lu dans la liste des rôles quand la règle a été changée avant le chargement de la page.
    expect(p.getByRole("checkbox", { name: "Retirer l’ancien rôle « 🦇 Batman » à ses 7 membres" })).toBeTruthy()
    await confirm(row("Vocal total"), "Valider", "Appliquer")
    expect(client.api.admin.applyRoleRule).toHaveBeenCalledWith(1, { confirm: true })
  })

  it("sans members.roles : la case de retrait de l’ancien rôle n’est pas proposée", async () => {
    server.getSessionUser.mockResolvedValue(me(["roles.manage"]))
    server.getRoleRules.mockResolvedValue([{ ...BATMAN, role_id: "400", role_name: "Fortnite", previous_role_id: "500" }])
    render(await AdminRulesPage())
    const p = await preview("Vocal total")
    expect(p.queryByRole("checkbox")).toBeNull()
    expect(p.getByText(/Donner ou retirer des rôles/)).toBeTruthy()
  })

  it("supprimer une règle : confirmation, ligne retirée", async () => {
    client.api.admin.deleteRoleRule.mockResolvedValue({ ok: true, reloaded: true })
    render(await AdminRulesPage())
    await confirm(row("Niveau XP"), "Supprimer", "Supprimer")
    expect(client.api.admin.deleteRoleRule).toHaveBeenCalledWith(3)
    await waitFor(() => expect(screen.queryByRole("row", { name: /^Niveau XP/ })).toBeNull())
    expect(screen.getByRole("status", { name: "Règles" }).textContent).toBe("Règle supprimée.")
  })

  it("suppression refusée (409) : texte de l’API", async () => {
    client.api.admin.deleteRoleRule.mockRejectedValue(new client.ApiError(409, "Conflit d’écriture"))
    render(await AdminRulesPage())
    await confirm(row("Niveau XP"), "Supprimer", "Supprimer")
    expect((await screen.findByRole("alert")).textContent).toMatch(/Conflit d’écriture/)
    expect(screen.getByRole("row", { name: /^Niveau XP/ })).toBeTruthy()
  })
})
