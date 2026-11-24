import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

vi.mock("server-only", () => ({}))
vi.mock("next/headers", () => ({ cookies: async () => ({ get: () => ({ value: "tok" }) }) }))
vi.mock("next/navigation", () => ({ usePathname: () => "/admin/salons" }))

const server = vi.hoisted(() => ({ getSessionUser: vi.fn(), getAdminChannels: vi.fn() }))
vi.mock("@/lib/api/server", () => server)

const client = vi.hoisted(() => ({
  api: {
    admin: {
      channels: vi.fn(),
      createChannel: vi.fn(),
      updateChannel: vi.fn(),
      deleteChannel: vi.fn(),
      previewChannelTemplate: vi.fn(),
      applyChannelTemplate: vi.fn(),
      previewStaffResync: vi.fn(),
      applyStaffResync: vi.fn(),
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

vi.mock("@/lib/auth-client", () => ({
  authClient: { useSession: { listen: () => () => {}, get: () => null }, signIn: { social: vi.fn() }, signOut: vi.fn() },
}))

import AdminLayout from "@/app/[locale]/admin/layout"
import AdminChannelsPage from "@/app/[locale]/admin/salons/page"
import { allowedSections } from "@/lib/admin-sections"

const channel = (id: string, name: string, type: string, parent_id: string | null, extra: Record<string, unknown> = {}) => ({
  id, name, type, position: 0, parent_id, overwrites: 0, template: null, visible_to_actor: true, ...extra,
})

const role = (id: string, name: string, position: number, assignable: boolean) => ({
  id, name, color: 0, position, managed: false, assignable,
})

const OVERVIEW = {
  channels: [
    channel("10", "accueil", "text", null),
    channel("20", "JEUX", "category", null),
    channel("21", "général-jeux", "text", "20", {
      template: { template: "role_required", roles: ["400"], applied_by: "1", applied_at: "2026-11-20T10:00:00Z" },
    }),
    channel("22", "Vocal jeux", "voice", "20"),
    channel("30", "staff-secret", "text", null, { visible_to_actor: false }),
  ],
  templates: ["public", "role_required", "announcements"],
  roles: [role("900", "Chef", 20, false), role("400", "Fortnite", 6, true), role("350", "Duo", 5, true)],
  actor: { top_position: 12, is_owner: false, permissions: ["channels.manage"], is_admin: false },
  staff_resync: null,
}

const ADMIN_OVERVIEW = {
  ...OVERVIEW,
  templates: ["public", "role_required", "announcements", "staff"],
  actor: { ...OVERVIEW.actor, is_admin: true },
  staff_resync: { pending: 2, channel_ids: ["10", "21"], staff_roles_set: true },
}

const PREVIEW = {
  channels: [
    {
      id: "10",
      name: "accueil",
      type: "text",
      changes: [
        { target_id: "400", target_type: "role", target_name: "Fortnite", action: "add", before: null, after: { allow: ["view_channel", "send_messages"], deny: [] } },
        { target_id: "1", target_type: "role", target_name: "@everyone", action: "update", before: { allow: ["view_channel"], deny: [] }, after: { allow: [], deny: ["view_channel"] } },
        { target_id: "500", target_type: "role", target_name: "Ancien rôle", action: "remove", before: { allow: ["view_channel"], deny: [] }, after: null },
      ],
    },
  ],
  count: 1,
  token: "tok-1",
}

const me = (permissions: string[], is_admin = false) => ({ user_id: "1", is_admin, is_redacteur: false, permissions })
const tree = () => within(screen.getByRole("list", { name: "Salons du serveur" }))

async function renderPage(overview: unknown = OVERVIEW, admin = false) {
  server.getSessionUser.mockResolvedValue(me(["channels.manage"], admin))
  server.getAdminChannels.mockResolvedValue(structuredClone(overview))
  client.api.admin.channels.mockResolvedValue(structuredClone(overview))
  render(await AdminChannelsPage())
}

/** Ouvre le panneau « Accès… » d'un salon. */
function openAccess(name: string) {
  fireEvent.click(screen.getByRole("button", { name: `Accès… « ${name} »` }))
  return within(screen.getByRole("region", { name: new RegExp(`Accès à .*${name}`) }))
}

async function click(button: HTMLElement) {
  await act(async () => {
    fireEvent.click(button)
  })
}

beforeEach(() => {
  server.getSessionUser.mockResolvedValue(me(["channels.manage"]))
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe("droits", () => {
  it("channels.manage ouvre la section « Salons » et son lien de navigation", async () => {
    expect(allowedSections(["channels.manage"]).map(s => [s.href, s.label])).toEqual([["/admin/salons", "Salons"]])
    render(await AdminLayout({ children: <p>contenu</p> }))
    const nav = within(screen.getByRole("navigation", { name: "Administration" }))
    expect(nav.getAllByRole("link").map(a => a.textContent)).toEqual(["Salons"])
  })

  it("sans channels.manage : 403 nommant le droit, l’arbre n’est pas lu", async () => {
    server.getSessionUser.mockResolvedValue(me(["roles.manage"]))
    render(await AdminChannelsPage())
    expect(screen.getByText("Erreur 403")).toBeTruthy()
    expect(screen.getByText(text => text.includes("« Gérer les salons »"))).toBeTruthy()
    expect(server.getAdminChannels).not.toHaveBeenCalled()
  })

  it("arbre illisible : message d’erreur, pas de liste", async () => {
    server.getAdminChannels.mockResolvedValue(null)
    render(await AdminChannelsPage())
    expect(screen.getByRole("alert").textContent).toMatch(/Salons illisibles/)
    expect(screen.queryByRole("list", { name: "Salons du serveur" })).toBeNull()
  })
})

describe("arborescence", () => {
  it("salons hors catégorie puis catégories et leurs salons, modèle mémorisé affiché", async () => {
    await renderPage()
    const items = tree().getAllByRole("listitem")
    expect(items[0].textContent).toMatch(/# accueil.*Modèle : —/)
    const children = within(screen.getByRole("list", { name: "Salons de « JEUX »" }))
    expect(children.getAllByRole("listitem").map(li => li.textContent)).toEqual([
      expect.stringMatching(/# général-jeux.*Modèle : Rôle requis \(Fortnite\)/),
      expect.stringMatching(/🔊 Vocal jeux.*Modèle : —/),
    ])
    // Pas de « Déplacer » pour une catégorie.
    expect(screen.queryByRole("button", { name: "Déplacer « JEUX »" })).toBeNull()
    expect(screen.getByRole("button", { name: "Déplacer « général-jeux »" })).toBeTruthy()
  })

  it("catégorie repliable au clavier (bouton aria-expanded)", async () => {
    await renderPage()
    const toggle = screen.getByRole("button", { name: "Replier « JEUX »" })
    expect(toggle.getAttribute("aria-expanded")).toBe("true")
    fireEvent.click(toggle)
    expect(screen.getByRole("button", { name: "Déplier « JEUX »" }).getAttribute("aria-expanded")).toBe("false")
    expect(screen.queryByRole("list", { name: "Salons de « JEUX »" })).toBeNull()
  })

  it("salon invisible pour l’acteur : entièrement masqué, nom absent du DOM", async () => {
    await renderPage()
    expect(document.body.textContent).not.toMatch(/staff-secret/)
    expect(document.body.textContent).not.toMatch(/vous ne voyez pas ce salon/)
  })

  it("salon visible dans une catégorie masquée : affiché hors catégorie", async () => {
    await renderPage({
      ...OVERVIEW,
      channels: [
        channel("10", "accueil", "text", null),
        channel("50", "secrète", "category", null, { visible_to_actor: false }),
        channel("51", "visible-dedans", "text", "50"),
      ],
    })
    expect(document.body.textContent).not.toMatch(/secrète/)
    expect(tree().getByRole("button", { name: "Renommer « visible-dedans »" })).toBeTruthy()
    // Parent absent de la liste (déjà retiré par l’API) : même traitement.
    cleanup()
    await renderPage({ ...OVERVIEW, channels: [channel("51", "visible-dedans", "text", "50")] })
    expect(tree().getByRole("button", { name: "Renommer « visible-dedans »" })).toBeTruthy()
  })

  it("catégorie vide : aucun aria-controls vers un identifiant inexistant", async () => {
    await renderPage({ ...OVERVIEW, channels: [...OVERVIEW.channels, channel("60", "VIDE", "category", null)] })
    const controlled = Array.from(document.querySelectorAll("[aria-controls]"))
    expect(controlled.length).toBeGreaterThan(0)
    for (const el of controlled) expect(document.getElementById(el.getAttribute("aria-controls")!)).not.toBeNull()
    expect(screen.getByRole("button", { name: "Replier « VIDE »" }).hasAttribute("aria-controls")).toBe(false)
  })
})

describe("création, renommage, déplacement", () => {
  it("crée un salon texte dans une catégorie puis relit l’arbre", async () => {
    await renderPage()
    client.api.admin.createChannel.mockResolvedValue({ id: "99", name: "tournoi", type: "text", parent_id: "20" })
    fireEvent.click(screen.getByRole("button", { name: "Nouveau salon" }))
    const form = within(screen.getByRole("region", { name: "Nouveau salon" }))
    fireEvent.change(form.getByLabelText("Nom"), { target: { value: "  tournoi " } })
    fireEvent.change(form.getByLabelText("Catégorie"), { target: { value: "20" } })
    await click(form.getByRole("button", { name: "Créer le salon" }))
    expect(client.api.admin.createChannel).toHaveBeenCalledWith({ name: "tournoi", type: "text", parent_id: "20" })
    expect(screen.getByRole("status", { name: "Salons" }).textContent).toBe("Salon « tournoi » créé.")
    expect(client.api.admin.channels).toHaveBeenCalled()
  })

  it("une catégorie se crée sans parent ; un nom vide est refusé sans appel", async () => {
    await renderPage()
    client.api.admin.createChannel.mockResolvedValue({ id: "98", name: "EVENTS", type: "category", parent_id: null })
    fireEvent.click(screen.getByRole("button", { name: "Nouveau salon" }))
    const form = within(screen.getByRole("region", { name: "Nouveau salon" }))
    await click(form.getByRole("button", { name: "Créer le salon" }))
    expect(form.getByRole("alert").textContent).toBe("Donnez un nom au salon.")
    expect(client.api.admin.createChannel).not.toHaveBeenCalled()
    fireEvent.change(form.getByLabelText("Type"), { target: { value: "category" } })
    expect(form.queryByLabelText("Catégorie")).toBeNull()
    fireEvent.change(form.getByLabelText("Nom"), { target: { value: "EVENTS" } })
    await click(form.getByRole("button", { name: "Créer le salon" }))
    expect(client.api.admin.createChannel).toHaveBeenCalledWith({ name: "EVENTS", type: "category" })
  })

  it("renomme et sort un salon de sa catégorie (parent_id null explicite)", async () => {
    await renderPage()
    client.api.admin.updateChannel.mockResolvedValue({ id: "21", name: "jeux-general", position: 0, parent_id: null })
    fireEvent.click(screen.getByRole("button", { name: "Renommer « général-jeux »" }))
    fireEvent.change(screen.getByLabelText("Nouveau nom de « général-jeux »"), { target: { value: "jeux-general" } })
    await click(screen.getByRole("button", { name: "Renommer" }))
    expect(client.api.admin.updateChannel).toHaveBeenCalledWith("21", { name: "jeux-general" })
    expect(screen.getByRole("status", { name: "Salons" }).textContent).toBe("Salon renommé en « jeux-general ».")

    fireEvent.click(screen.getByRole("button", { name: "Déplacer « général-jeux »" }))
    fireEvent.change(screen.getByLabelText("Catégorie de « général-jeux »"), { target: { value: "" } })
    await click(screen.getByRole("button", { name: "Déplacer" }))
    expect(client.api.admin.updateChannel).toHaveBeenLastCalledWith("21", { parent_id: null })
  })

  it("403 du bot (salon non visible) affiché tel que rédigé par l’API", async () => {
    await renderPage()
    client.api.admin.updateChannel.mockRejectedValue(new client.ApiError(403, "Vous ne voyez pas ce salon dans Discord"))
    fireEvent.click(screen.getByRole("button", { name: "Renommer « accueil »" }))
    fireEvent.change(screen.getByLabelText("Nouveau nom de « accueil »"), { target: { value: "bienvenue" } })
    await click(screen.getByRole("button", { name: "Renommer" }))
    expect(screen.getByRole("alert").textContent).toBe("Vous ne voyez pas ce salon dans Discord")
  })
})

describe("suppression avec nom retapé", () => {
  it("bouton inactif tant que le nom exact n’est pas retapé ; envoie le nom saisi", async () => {
    await renderPage()
    client.api.admin.deleteChannel.mockResolvedValue({ ok: true })
    fireEvent.click(screen.getByRole("button", { name: "Supprimer « accueil »" }))
    const input = screen.getByLabelText("Retapez « accueil » pour supprimer définitivement ce salon")
    const submit = screen.getByRole("button", { name: "Supprimer définitivement" }) as HTMLButtonElement
    expect(submit.disabled).toBe(true)
    fireEvent.change(input, { target: { value: "Accueil" } })
    expect(submit.disabled).toBe(true)
    fireEvent.change(input, { target: { value: " accueil " } })
    expect(submit.disabled).toBe(false)
    await click(submit)
    expect(client.api.admin.deleteChannel).toHaveBeenCalledWith("10", "accueil")
    expect(screen.getByRole("status", { name: "Salons" }).textContent).toBe("Salon « accueil » supprimé.")
  })

  it("catégorie non vide : avertissement, puis refus 409 « videz d’abord la catégorie » affiché", async () => {
    await renderPage()
    client.api.admin.deleteChannel.mockRejectedValue(
      new client.ApiError(409, "Videz d'abord la catégorie : elle contient 2 salon(s)"),
    )
    fireEvent.click(screen.getByRole("button", { name: "Supprimer « JEUX »" }))
    expect(screen.getByText(/Cette catégorie contient 2 salons/)).toBeTruthy()
    fireEvent.change(screen.getByLabelText("Retapez « JEUX » pour supprimer définitivement ce salon"), { target: { value: "JEUX" } })
    await click(screen.getByRole("button", { name: "Supprimer définitivement" }))
    expect(screen.getByRole("alert").textContent).toBe("Refusé : Videz d'abord la catégorie : elle contient 2 salon(s).")
  })
})

describe("modèles d’accès", () => {
  it("non admin : pas de modèle Staff ; seuls les rôles sous l’acteur sont proposés", async () => {
    await renderPage()
    const panel = openAccess("accueil")
    expect(panel.getAllByRole("radio").map(r => (r as HTMLInputElement).value)).toEqual(["public", "role_required", "announcements"])
    fireEvent.click(panel.getByRole("radio", { name: /Rôle requis/ }))
    expect(panel.getAllByRole("checkbox").map(c => c.parentElement?.textContent)).toEqual(["@Fortnite", "@Duo"])
  })

  it("rôle requis sans rôle : refusé sans appel ; aperçu puis application avec le jeton", async () => {
    await renderPage()
    client.api.admin.previewChannelTemplate.mockResolvedValue(structuredClone(PREVIEW))
    client.api.admin.applyChannelTemplate.mockResolvedValue({ applied: 1, failed: [], memo_failed: [] })
    const panel = openAccess("accueil")
    fireEvent.click(panel.getByRole("radio", { name: /Rôle requis/ }))
    await click(panel.getByRole("button", { name: "Voir l’aperçu" }))
    expect(panel.getByRole("alert").textContent).toBe("Choisissez au moins un rôle.")
    expect(client.api.admin.previewChannelTemplate).not.toHaveBeenCalled()

    fireEvent.click(panel.getByRole("checkbox", { name: "@Fortnite" }))
    await click(panel.getByRole("button", { name: "Voir l’aperçu" }))
    expect(client.api.admin.previewChannelTemplate).toHaveBeenCalledWith("10", {
      template: "role_required",
      roles: ["400"],
      sync_children: false,
    })
    const lines = within(panel.getByRole("list", { name: "Aperçu des changements" }))
      .getAllByRole("listitem")
      .slice(1)
      .map(li => li.textContent)
    expect(lines).toEqual([
      "+ ajout : Fortnite : voir oui, écrire oui",
      "~ modification : @everyone : voir oui → non",
      "− retrait : Ancien rôle : surcharge retirée",
    ])
    expect(client.api.admin.applyChannelTemplate).not.toHaveBeenCalled()

    await click(panel.getByRole("button", { name: "Appliquer" }))
    expect(client.api.admin.applyChannelTemplate).toHaveBeenCalledWith("10", {
      template: "role_required",
      roles: ["400"],
      sync_children: false,
      token: "tok-1",
    })
    expect(screen.getByRole("status", { name: "Salons" }).textContent).toBe("Accès appliqué à 1 salon.")
    expect(client.api.admin.channels).toHaveBeenCalled()
  })

  it("changer un choix après l’aperçu l’invalide (jeton lié aux paramètres)", async () => {
    await renderPage()
    client.api.admin.previewChannelTemplate.mockResolvedValue(structuredClone(PREVIEW))
    const panel = openAccess("accueil")
    fireEvent.click(panel.getByRole("radio", { name: /Public/ }))
    await click(panel.getByRole("button", { name: "Voir l’aperçu" }))
    expect(panel.getByRole("button", { name: "Appliquer" })).toBeTruthy()
    fireEvent.click(panel.getByRole("radio", { name: /Annonces/ }))
    expect(panel.queryByRole("button", { name: "Appliquer" })).toBeNull()
  })

  it("409 jeton périmé : message de l’API affiché, aperçu retiré pour être refait", async () => {
    await renderPage()
    client.api.admin.previewChannelTemplate.mockResolvedValue(structuredClone(PREVIEW))
    client.api.admin.applyChannelTemplate.mockRejectedValue(
      new client.ApiError(409, "L'aperçu n'est plus à jour : l'état du salon a changé. Refaites l'aperçu."),
    )
    const panel = openAccess("accueil")
    fireEvent.click(panel.getByRole("radio", { name: /Public/ }))
    await click(panel.getByRole("button", { name: "Voir l’aperçu" }))
    await click(panel.getByRole("button", { name: "Appliquer" }))
    expect(panel.getByRole("alert").textContent).toBe(
      "Refusé : L'aperçu n'est plus à jour : l'état du salon a changé. Refaites l'aperçu.",
    )
    expect(panel.queryByRole("button", { name: "Appliquer" })).toBeNull()
  })

  it("403 « Public » sur un salon que l’acteur ne voit pas, 403 rôle au-dessus : affichés à l’aperçu", async () => {
    await renderPage()
    client.api.admin.previewChannelTemplate.mockRejectedValueOnce(
      new client.ApiError(403, "Vous ne voyez pas ce salon dans Discord : impossible d'en changer l'accès"),
    )
    const panel = openAccess("accueil")
    fireEvent.click(panel.getByRole("radio", { name: /Public/ }))
    await click(panel.getByRole("button", { name: "Voir l’aperçu" }))
    expect(panel.getByRole("alert").textContent).toMatch(/^Vous ne voyez pas ce salon/)

    client.api.admin.previewChannelTemplate.mockRejectedValueOnce(
      new client.ApiError(403, "Le rôle « Fortnite » est au niveau du vôtre ou au-dessus : impossible de l'utiliser"),
    )
    fireEvent.click(panel.getByRole("radio", { name: /Annonces/ }))
    fireEvent.click(panel.getByRole("checkbox", { name: "@Fortnite" }))
    await click(panel.getByRole("button", { name: "Voir l’aperçu" }))
    expect(panel.getByRole("alert").textContent).toMatch(/^Le rôle « Fortnite » est au niveau du vôtre/)
    expect(client.api.admin.applyChannelTemplate).not.toHaveBeenCalled()
  })

  it("catégorie : case de synchronisation avec le nombre de salons ; confirmation chiffrée", async () => {
    await renderPage()
    client.api.admin.previewChannelTemplate.mockResolvedValue({ ...structuredClone(PREVIEW), count: 3 })
    client.api.admin.applyChannelTemplate.mockResolvedValue({ applied: 3, failed: [], memo_failed: [] })
    const panel = openAccess("JEUX")
    fireEvent.click(panel.getByRole("radio", { name: /Public/ }))
    fireEvent.click(panel.getByRole("checkbox", { name: "Appliquer aussi aux salons de la catégorie (2)" }))
    await click(panel.getByRole("button", { name: "Voir l’aperçu" }))
    expect(client.api.admin.previewChannelTemplate).toHaveBeenCalledWith("20", { template: "public", roles: [], sync_children: true })
    expect(panel.getByRole("heading", { name: "Aperçu (3 salons)" })).toBeTruthy()
    await click(panel.getByRole("button", { name: "Appliquer aux 3 salons" }))
    expect(client.api.admin.applyChannelTemplate).toHaveBeenCalledWith("20", {
      template: "public",
      roles: [],
      sync_children: true,
      token: "tok-1",
    })
    expect(screen.getByRole("status", { name: "Salons" }).textContent).toBe("Accès appliqué à 3 salons.")
  })

  it("application longue : « en cours… » sans bloquer ; 504 : l’action se termine peut-être encore", async () => {
    await renderPage()
    client.api.admin.previewChannelTemplate.mockResolvedValue(structuredClone(PREVIEW))
    let reject!: (e: unknown) => void
    client.api.admin.applyChannelTemplate.mockReturnValue(new Promise((_, r) => (reject = r)))
    const panel = openAccess("accueil")
    fireEvent.click(panel.getByRole("radio", { name: /Public/ }))
    await click(panel.getByRole("button", { name: "Voir l’aperçu" }))
    await click(panel.getByRole("button", { name: "Appliquer" }))
    expect(panel.getByRole("status").textContent).toMatch(/^Application en cours…/)
    // Le reste de la page reste utilisable.
    expect((screen.getByRole("button", { name: "Nouveau salon" }) as HTMLButtonElement).disabled).toBe(false)
    await act(async () => reject(new client.ApiError(504, "Gateway Timeout")))
    expect(panel.getByRole("alert").textContent).toBe(
      "L’action se termine peut-être encore : rechargez la page dans un instant pour voir l’état des salons.",
    )
    expect(panel.getByRole("status").textContent).toBe("")
  })

  it("échec partiel et memo_failed : avertissements affichés", async () => {
    await renderPage()
    client.api.admin.previewChannelTemplate.mockResolvedValue({ ...structuredClone(PREVIEW), count: 3 })
    client.api.admin.applyChannelTemplate.mockResolvedValue({
      applied: 2,
      failed: [{ id: "22", name: "Vocal jeux", error: "Permission refusée" }],
      memo_failed: ["21"],
    })
    const panel = openAccess("JEUX")
    fireEvent.click(panel.getByRole("radio", { name: /Public/ }))
    await click(panel.getByRole("button", { name: "Voir l’aperçu" }))
    await click(panel.getByRole("button", { name: "Appliquer aux 3 salons" }))
    const warnings = within(screen.getByRole("alert", { name: "Avertissements" })).getAllByRole("listitem")
    expect(warnings.map(w => w.textContent)).toEqual([
      "« Vocal jeux » : Permission refusée",
      "1 salon appliqué(s) sur Discord, mais non mémorisé(s) pour la resynchronisation Staff.",
    ])
  })
})

describe("resynchronisation Staff", () => {
  it("non admin : ni bandeau ni modèle Staff", async () => {
    await renderPage()
    expect(screen.queryByRole("region", { name: "Rôles Staff modifiés" })).toBeNull()
    expect(screen.queryByRole("button", { name: "Mettre à jour les salons Staff" })).toBeNull()
  })

  it("admin, staff_roles changé : bandeau, aperçu puis application avec le jeton", async () => {
    await renderPage(ADMIN_OVERVIEW, true)
    const after = { ...ADMIN_OVERVIEW, staff_resync: { pending: 0, channel_ids: [], staff_roles_set: true } }
    client.api.admin.channels.mockResolvedValue(structuredClone(after))
    client.api.admin.previewStaffResync.mockResolvedValue({ ...structuredClone(PREVIEW), count: 2, token: "staff-tok" })
    client.api.admin.applyStaffResync.mockResolvedValue({ applied: 2, failed: [], memo_failed: [] })

    const banner = within(screen.getByRole("region", { name: "Rôles Staff modifiés" }))
    expect(banner.getByText(/2 salons « Staff » gardent les anciens rôles Staff/)).toBeTruthy()
    await click(banner.getByRole("button", { name: "Mettre à jour les salons Staff" }))
    expect(client.api.admin.previewStaffResync).toHaveBeenCalled()
    expect(banner.getByRole("list", { name: "Aperçu des changements" })).toBeTruthy()
    expect(client.api.admin.applyStaffResync).not.toHaveBeenCalled()
    await click(banner.getByRole("button", { name: "Appliquer aux 2 salons" }))
    expect(client.api.admin.applyStaffResync).toHaveBeenCalledWith("staff-tok")
    expect(screen.getByRole("status", { name: "Salons" }).textContent).toBe("Accès appliqué à 2 salons.")
    await waitFor(() => expect(screen.queryByRole("region", { name: "Rôles Staff modifiés" })).toBeNull())
  })

  it("admin : le modèle Staff est proposé", async () => {
    await renderPage(ADMIN_OVERVIEW, true)
    const panel = openAccess("accueil")
    expect(panel.getByRole("radio", { name: /Staff/ })).toBeTruthy()
  })

  it("aucun rôle Staff réglé : pas de bouton, renvoi aux Réglages", async () => {
    await renderPage({ ...ADMIN_OVERVIEW, staff_resync: { pending: 1, channel_ids: ["10"], staff_roles_set: false } }, true)
    const banner = within(screen.getByRole("region", { name: "Rôles Staff modifiés" }))
    expect(banner.queryByRole("button")).toBeNull()
    expect(banner.getByText(/Aucun rôle Staff n’est réglé/)).toBeTruthy()
  })
})
