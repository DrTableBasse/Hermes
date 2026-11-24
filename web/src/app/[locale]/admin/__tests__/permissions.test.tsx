import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

vi.mock("server-only", () => ({}))
vi.mock("next/headers", () => ({ cookies: async () => ({ get: () => ({ value: "tok" }) }) }))
vi.mock("next/navigation", () => ({ usePathname: () => "/admin/permissions" }))

const server = vi.hoisted(() => ({
  getSessionUser: vi.fn(),
  getDiscordPermissions: vi.fn(),
  getCommandPermissions: vi.fn(),
}))
vi.mock("@/lib/api/server", () => server)

const client = vi.hoisted(() => ({
  api: { admin: { putRolePermissions: vi.fn(), putCommandPermissions: vi.fn() } },
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

import AdminPermissionsPage from "@/app/[locale]/admin/permissions/page"
import { ADMIN_SECTIONS, allowedSections } from "@/lib/admin-sections"

const role = (id: string, name: string, position: number, extra: Record<string, unknown> = {}) => ({
  id,
  name,
  position,
  managed: false,
  is_default: false,
  permissions: [] as string[],
  editable: false,
  refusal: null as string | null,
  editable_flags: [] as string[],
  ...extra,
})

const ACTOR_FLAGS = ["kick_members", "manage_messages", "send_messages"]

const DISCORD = {
  families: [],
  roles: [
    role("900", "Chef", 15, { permissions: ["ban_members"], refusal: "Ce rôle n'est pas sous votre rôle le plus haut" }),
    role("400", "Modérateur", 5, { permissions: ["kick_members"], editable: true, editable_flags: ACTOR_FLAGS }),
    role("300", "Bot Musique", 4, { managed: true, refusal: "Ce rôle est géré par une intégration et ne peut pas être modifié" }),
    role("1", "@everyone", 0, {
      is_default: true,
      refusal: "Seul le propriétaire du serveur peut modifier les permissions de @everyone",
    }),
  ],
  actor: { is_owner: false, top_position: 10, permissions: ACTOR_FLAGS, is_admin: false },
}

const command = (name: string, extra: Record<string, unknown> = {}) => ({
  name,
  description: `Description de ${name}`,
  admin_only: false,
  native_protected: false,
  roles: [] as Array<{ id: string; name: string | null; deleted: boolean }>,
  editable: true,
  ...extra,
})

const COMMANDS = {
  commands: [
    command("warn", { admin_only: true, editable: false }),
    command("kick", {
      admin_only: true,
      roles: [
        { id: "900", name: "Chef", deleted: false },
        { id: "555", name: null, deleted: true },
      ],
    }),
    command("blague"),
    command("meteo", { roles: [{ id: "400", name: "Modérateur", deleted: false }] }),
  ],
  roles: [
    { id: "900", name: "Chef", color: 0, position: 15, assignable: false },
    { id: "400", name: "Modérateur", color: 0, position: 5, assignable: true },
    { id: "200", name: "Membre", color: 0, position: 2, assignable: true },
  ],
  actor: { is_owner: false, top_position: 10, is_admin: true },
}

const me = (permissions: string[]) => ({ user_id: "1", is_admin: false, is_redacteur: false, permissions })
const region = (name: string | RegExp) => within(screen.getByRole("region", { name }))
const box = (name: string | RegExp) => screen.getByRole("checkbox", { name }) as HTMLInputElement

async function renderPage() {
  render(await AdminPermissionsPage())
}

function openHermes() {
  fireEvent.click(screen.getByRole("tab", { name: "Hermes" }))
}

beforeEach(() => {
  server.getSessionUser.mockResolvedValue(me(["permissions.manage"]))
  server.getDiscordPermissions.mockResolvedValue(structuredClone(DISCORD))
  server.getCommandPermissions.mockResolvedValue(structuredClone(COMMANDS))
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe("droits de la page /admin/permissions", () => {
  it("section « Permissions » : droit permissions.manage, après « Accès »", () => {
    expect(ADMIN_SECTIONS.find(s => s.href === "/admin/permissions")?.permission).toBe("permissions.manage")
    expect(allowedSections(["permissions.manage"]).map(s => s.label)).toEqual(["Accès", "Permissions"])
    expect(allowedSections(["roles.manage"]).some(s => s.href === "/admin/permissions")).toBe(false)
  })

  it("sans permissions.manage : 403, aucune API de permissions lue", async () => {
    server.getSessionUser.mockResolvedValue(me(["roles.manage", "moderation.view"]))
    await renderPage()
    expect(screen.getByText("Erreur 403")).toBeTruthy()
    expect(server.getDiscordPermissions).not.toHaveBeenCalled()
    expect(server.getCommandPermissions).not.toHaveBeenCalled()
    expect(screen.queryByRole("tablist")).toBeNull()
  })

  it("API muettes : erreur dans chaque onglet, aucune case", async () => {
    server.getDiscordPermissions.mockResolvedValue(null)
    server.getCommandPermissions.mockResolvedValue(null)
    await renderPage()
    expect(screen.getByRole("alert").textContent).toMatch(/Permissions Discord illisibles/)
    expect(screen.queryAllByRole("checkbox")).toHaveLength(0)
    openHermes()
    expect(screen.getByRole("alert").textContent).toMatch(/Commandes illisibles/)
  })
})

describe("onglets", () => {
  it("tablist ARIA : aria-controls vers un panneau présent, flèches et Début/Fin, lien Site → /admin/acces", async () => {
    await renderPage()
    expect(server.getDiscordPermissions).toHaveBeenCalledWith("tok")
    expect(server.getCommandPermissions).toHaveBeenCalledWith("tok")
    const tabs = within(screen.getByRole("tablist", { name: "Permissions" })).getAllByRole("tab")
    expect(tabs.map(t => t.textContent)).toEqual(["Discord", "Hermes"])
    for (const t of tabs) {
      const panel = document.getElementById(t.getAttribute("aria-controls") ?? "")
      expect(panel?.getAttribute("role")).toBe("tabpanel")
      expect(panel?.getAttribute("aria-labelledby")).toBe(t.id)
    }
    expect(tabs[0].getAttribute("aria-selected")).toBe("true")
    expect(tabs[1].tabIndex).toBe(-1)

    fireEvent.keyDown(tabs[0], { key: "ArrowRight" })
    expect(tabs[1].getAttribute("aria-selected")).toBe("true")
    expect(document.activeElement).toBe(tabs[1])
    expect(screen.getByRole("heading", { name: "Réservées aux admins" })).toBeTruthy()
    expect(screen.queryByRole("heading", { name: "Permissions Discord" })).toBeNull()
    fireEvent.keyDown(tabs[1], { key: "ArrowRight" })
    expect(tabs[0].getAttribute("aria-selected")).toBe("true")
    fireEvent.keyDown(tabs[0], { key: "End" })
    expect(tabs[1].getAttribute("aria-selected")).toBe("true")
    fireEvent.keyDown(tabs[1], { key: "Home" })
    expect(tabs[0].getAttribute("aria-selected")).toBe("true")

    expect(screen.getByRole("link", { name: "Site → Accès" }).getAttribute("href")).toBe("/admin/acces")
  })
})

describe("onglet Discord", () => {
  it("premier rôle modifiable choisi ; rôles verrouillés nommés dans la liste", async () => {
    await renderPage()
    const select = screen.getByRole("combobox", { name: "Rôle" }) as HTMLSelectElement
    expect(select.value).toBe("400")
    expect([...select.options].map(o => o.textContent)).toEqual([
      "Chef — rôle au-dessus du vôtre",
      "Modérateur",
      "Bot Musique — rôle d’intégration",
      "@everyone — réservé au propriétaire",
    ])
  })

  it("familles en fieldset/legend ; case non possédée désactivée avec sa raison ; Administrateur réservé", async () => {
    await renderPage()
    expect(screen.getByRole("group", { name: "Membres" })).toBeTruthy()
    expect(screen.getByRole("group", { name: "Avancé" })).toBeTruthy()
    expect(box("Expulser des membres").checked).toBe(true)
    expect(box("Expulser des membres").disabled).toBe(false)
    const ban = box("Bannir des membres (vous n’avez pas cette permission)")
    expect(ban.disabled).toBe(true)
    expect(ban.checked).toBe(false)
    const admin = box("Administrateur (réservé au propriétaire)")
    expect(admin.disabled).toBe(true)
  })

  it("rôle au-dessus, d’intégration ou @everyone : toutes les cases désactivées, raison de l’API affichée", async () => {
    await renderPage()
    const select = screen.getByRole("combobox", { name: "Rôle" })
    for (const [id, text] of [
      ["900", /rôle au-dessus du vôtre.*pas sous votre rôle le plus haut/],
      ["300", /rôle d’intégration.*géré par une intégration/],
      ["1", /réservé au propriétaire.*@everyone/],
    ] as const) {
      fireEvent.change(select, { target: { value: id } })
      expect(screen.getByText(text)).toBeTruthy()
      const boxes = screen.getAllByRole("checkbox") as HTMLInputElement[]
      expect(boxes.every(b => b.disabled)).toBe(true)
      expect(screen.queryByRole("button", { name: "Enregistrer" })).toBeNull()
    }
    fireEvent.change(select, { target: { value: "900" } })
    expect(box(/^Bannir des membres/).checked).toBe(true)
  })

  it("Enregistrer : récapitulatif avant/après en français, puis confirmation et envoi de l’ensemble complet", async () => {
    client.api.admin.putRolePermissions.mockResolvedValue({
      changed: true,
      role: { ...DISCORD.roles[1], permissions: ["manage_messages", "send_messages"] },
    })
    await renderPage()
    const save = screen.getByRole("button", { name: "Enregistrer" }) as HTMLButtonElement
    expect(save.disabled).toBe(true)
    fireEvent.click(box("Expulser des membres"))
    fireEvent.click(box("Gérer les messages"))
    fireEvent.click(box("Envoyer des messages"))
    fireEvent.click(save)

    const recap = within(screen.getByRole("group", { name: "Récapitulatif pour « Modérateur »" }))
    const lists = recap.getAllByRole("list").map(l => within(l).getAllByRole("listitem").map(li => li.textContent))
    // Ordre du catalogue : Messages (Envoyer avant Gérer) ; retirées : Expulser.
    expect(lists).toEqual([["Envoyer des messages", "Gérer les messages"], ["Expulser des membres"]])
    expect(recap.getByText("Permissions ajoutées")).toBeTruthy()
    expect(recap.getByText("Permissions retirées")).toBeTruthy()
    expect(client.api.admin.putRolePermissions).not.toHaveBeenCalled()
    expect(box("Gérer les messages").disabled).toBe(true)

    await act(async () => {
      fireEvent.click(recap.getByRole("button", { name: "Confirmer l’enregistrement" }))
    })
    expect(client.api.admin.putRolePermissions).toHaveBeenCalledWith("400", ["send_messages", "manage_messages"], false)
    expect(screen.getByRole("status").textContent).toBe("Permissions de « Modérateur » enregistrées sur Discord.")
    expect(box("Expulser des membres").checked).toBe(false)
    expect((screen.getByRole("button", { name: "Enregistrer" }) as HTMLButtonElement).disabled).toBe(true)
  })

  it("récapitulatif annulé : rien n’est envoyé, les changements restent modifiables", async () => {
    await renderPage()
    fireEvent.click(box("Gérer les messages"))
    fireEvent.click(screen.getByRole("button", { name: "Enregistrer" }))
    const recap = screen.getByRole("group", { name: /Récapitulatif/ })
    expect(within(recap).getByText("Aucune")).toBeTruthy()
    fireEvent.click(within(recap).getByRole("button", { name: "Annuler" }))
    expect(screen.queryByRole("group", { name: /Récapitulatif/ })).toBeNull()
    expect(box("Gérer les messages").checked).toBe(true)
    expect(client.api.admin.putRolePermissions).not.toHaveBeenCalled()
  })

  it("refus de l’API (403 escalade) : message de l’API affiché, case conservée", async () => {
    client.api.admin.putRolePermissions.mockRejectedValue(
      new client.ApiError(403, "Tu ne peux pas accorder la permission « Gérer les messages » : tu ne la possèdes pas."),
    )
    await renderPage()
    fireEvent.click(box("Gérer les messages"))
    fireEvent.click(screen.getByRole("button", { name: "Enregistrer" }))
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Confirmer l’enregistrement" }))
    })
    expect(screen.getByRole("alert").textContent).toBe(
      "Tu ne peux pas accorder la permission « Gérer les messages » : tu ne la possèdes pas.",
    )
    expect(box("Gérer les messages").checked).toBe(true)
  })

  it("bot trop lent (504) : détail de l’API gardé", async () => {
    client.api.admin.putRolePermissions.mockRejectedValue(
      new client.ApiError(504, "Le bot n'a pas répondu à temps : rechargez la page pour voir l'état actuel"),
    )
    await renderPage()
    fireEvent.click(box("Gérer les messages"))
    fireEvent.click(screen.getByRole("button", { name: "Enregistrer" }))
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Confirmer l’enregistrement" }))
    })
    expect(screen.getByRole("alert").textContent).toMatch(/n'a pas répondu à temps/)
  })

  it("propriétaire : Administrateur ouvre une confirmation explicite et envoie confirm_administrator", async () => {
    const data = structuredClone(DISCORD)
    data.actor = { is_owner: true, top_position: 99, permissions: [], is_admin: true }
    data.roles[1].editable_flags = ["kick_members", "ban_members", "administrator"]
    server.getDiscordPermissions.mockResolvedValue(data)
    client.api.admin.putRolePermissions.mockResolvedValue({
      changed: true,
      role: { ...data.roles[1], permissions: ["kick_members", "administrator"] },
    })
    await renderPage()
    const admin = box("Administrateur")
    expect(admin.disabled).toBe(false)

    fireEvent.click(admin)
    const ask = within(screen.getByRole("group", { name: "Accorder « Administrateur » ?" }))
    expect(box("Administrateur").checked).toBe(false)
    fireEvent.click(ask.getByRole("button", { name: "Annuler" }))
    expect(box("Administrateur").checked).toBe(false)

    fireEvent.click(box("Administrateur"))
    fireEvent.click(
      within(screen.getByRole("group", { name: "Accorder « Administrateur » ?" })).getByRole("button", {
        name: "Accorder Administrateur",
      }),
    )
    expect(box("Administrateur").checked).toBe(true)
    fireEvent.click(screen.getByRole("button", { name: "Enregistrer" }))
    const recap = within(screen.getByRole("group", { name: /Récapitulatif/ }))
    expect(recap.getAllByRole("listitem").map(li => li.textContent)).toEqual(["Administrateur"])
    await act(async () => {
      fireEvent.click(recap.getByRole("button", { name: "Confirmer l’enregistrement" }))
    })
    expect(client.api.admin.putRolePermissions).toHaveBeenCalledWith("400", ["kick_members", "administrator"], true)
  })

  it("non-propriétaire administrateur : peut retirer Administrateur, l’envoi ne confirme rien", async () => {
    const data = structuredClone(DISCORD)
    data.actor = { ...data.actor, permissions: ["administrator"] }
    data.roles[1].permissions = ["administrator"]
    data.roles[1].editable_flags = ["kick_members", "administrator"]
    server.getDiscordPermissions.mockResolvedValue(data)
    client.api.admin.putRolePermissions.mockResolvedValue({ changed: true, role: { ...data.roles[1], permissions: [] } })
    await renderPage()
    fireEvent.click(box("Administrateur"))
    expect(screen.queryByRole("group", { name: /Accorder/ })).toBeNull()
    fireEvent.click(screen.getByRole("button", { name: "Enregistrer" }))
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Confirmer l’enregistrement" }))
    })
    expect(client.api.admin.putRolePermissions).toHaveBeenCalledWith("400", [], false)
  })
})

describe("onglet Hermes", () => {
  it("commandes groupées ; liste vide : « Tout le monde » ou « Administrateurs seulement »", async () => {
    await renderPage()
    openHermes()
    const admin = region("Réservées aux admins")
    const open = region("Ouvertes")
    expect(admin.getAllByRole("heading", { level: 3 }).map(h => h.textContent)).toEqual(["/warn", "/kick"])
    expect(open.getAllByRole("heading", { level: 3 }).map(h => h.textContent)).toEqual(["/blague", "/meteo"])
    expect(region("/warn").getByText("Administrateurs seulement")).toBeTruthy()
    expect(region("/blague").getByText("Tout le monde")).toBeTruthy()
    expect(region("/meteo").getByText("Seulement : Modérateur (et les administrateurs)")).toBeTruthy()
  })

  it("commande admin non modifiable par l’acteur : aucune commande de modification", async () => {
    await renderPage()
    openHermes()
    const warn = region("/warn")
    expect(warn.getByText(/Réservée aux administrateurs du site/)).toBeTruthy()
    expect(warn.queryByRole("combobox")).toBeNull()
    expect(warn.queryAllByRole("button")).toHaveLength(0)
  })

  it("restreindre une commande ouverte : seuls les rôles sous l’acteur sont proposés, liste envoyée", async () => {
    client.api.admin.putCommandPermissions.mockResolvedValue({
      command: "blague",
      role_ids: ["200"],
      changed: true,
      reload_failed: false,
    })
    await renderPage()
    openHermes()
    const blague = region("/blague")
    const select = blague.getByRole("combobox", { name: "Rôle à autoriser pour /blague" }) as HTMLSelectElement
    expect([...select.options].map(o => o.value)).toEqual(["", "400", "200"])
    fireEvent.change(select, { target: { value: "200" } })
    fireEvent.click(blague.getByRole("button", { name: "Restreindre à ce rôle" }))
    expect(blague.getByText("Seulement : Membre (et les administrateurs)")).toBeTruthy()
    await act(async () => {
      fireEvent.click(blague.getByRole("button", { name: "Enregistrer" }))
    })
    expect(client.api.admin.putCommandPermissions).toHaveBeenCalledWith("blague", ["200"])
    expect(blague.getByRole("status").textContent).toBe("/blague : Seulement : Membre (et les administrateurs).")
  })

  it("liste blanche vidée : la commande redevient ouverte à tout le monde", async () => {
    client.api.admin.putCommandPermissions.mockResolvedValue({
      command: "meteo",
      role_ids: [],
      changed: true,
      reload_failed: false,
    })
    await renderPage()
    openHermes()
    const meteo = region("/meteo")
    fireEvent.click(meteo.getByRole("button", { name: "Retirer Modérateur" }))
    expect(meteo.getByText("Tout le monde")).toBeTruthy()
    expect(meteo.getByText(/de nouveau ouverte à tout le monde/)).toBeTruthy()
    await act(async () => {
      fireEvent.click(meteo.getByRole("button", { name: "Enregistrer" }))
    })
    expect(client.api.admin.putCommandPermissions).toHaveBeenCalledWith("meteo", [])
    expect(meteo.getByRole("status").textContent).toBe("/meteo : Tout le monde.")
  })

  it("rôle au-dessus de l’acteur : non retirable ; rôle supprimé : retirable (nettoyage)", async () => {
    client.api.admin.putCommandPermissions.mockResolvedValue({
      command: "kick",
      role_ids: ["900"],
      changed: true,
      reload_failed: false,
    })
    await renderPage()
    openHermes()
    const kick = region("/kick")
    expect(kick.queryByRole("button", { name: "Retirer Chef" })).toBeNull()
    expect(kick.getByText("(rôle au-dessus du vôtre)")).toBeTruthy()
    expect(kick.getByText("Administrateurs et : Chef, Rôle supprimé (555)")).toBeTruthy()
    fireEvent.click(kick.getByRole("button", { name: "Retirer Rôle supprimé (555)" }))
    await act(async () => {
      fireEvent.click(kick.getByRole("button", { name: "Enregistrer" }))
    })
    expect(client.api.admin.putCommandPermissions).toHaveBeenCalledWith("kick", ["900"])
  })

  it("reload_failed : enregistré, avertissement de relance du bot", async () => {
    client.api.admin.putCommandPermissions.mockResolvedValue({
      command: "blague",
      role_ids: ["400"],
      changed: true,
      reload_failed: true,
    })
    await renderPage()
    openHermes()
    const blague = region("/blague")
    fireEvent.change(blague.getByRole("combobox"), { target: { value: "400" } })
    fireEvent.click(blague.getByRole("button", { name: "Restreindre à ce rôle" }))
    await act(async () => {
      fireEvent.click(blague.getByRole("button", { name: "Enregistrer" }))
    })
    expect(blague.getByRole("alert").textContent).toBe(
      "Enregistré, mais le bot ne l’a pas encore pris en compte : réessayez ou redémarrez le bot.",
    )
    expect(blague.queryByRole("button", { name: "Enregistrer" })).toBeNull()
  })

  it("reload_failed : « Réessayer » renvoie la liste enregistrée, l’avertissement disparaît au succès", async () => {
    client.api.admin.putCommandPermissions.mockResolvedValueOnce({
      command: "blague",
      role_ids: ["400"],
      changed: true,
      reload_failed: true,
    })
    await renderPage()
    openHermes()
    const blague = region("/blague")
    fireEvent.change(blague.getByRole("combobox"), { target: { value: "400" } })
    fireEvent.click(blague.getByRole("button", { name: "Restreindre à ce rôle" }))
    await act(async () => {
      fireEvent.click(blague.getByRole("button", { name: "Enregistrer" }))
    })
    expect(blague.getByRole("alert")).toBeTruthy()

    let finish: (v: unknown) => void = () => {}
    client.api.admin.putCommandPermissions.mockReturnValueOnce(new Promise(r => (finish = r)))
    await act(async () => {
      fireEvent.click(blague.getByRole("button", { name: "Réessayer" }))
    })
    expect(client.api.admin.putCommandPermissions).toHaveBeenLastCalledWith("blague", ["400"])
    expect((blague.getByRole("button", { name: "Nouvelle tentative…" }) as HTMLButtonElement).disabled).toBe(true)

    await act(async () => {
      finish({ command: "blague", role_ids: ["400"], changed: false, reload_failed: false })
    })
    expect(blague.queryByRole("alert")).toBeNull()
    expect(blague.queryByRole("button", { name: "Réessayer" })).toBeNull()
  })

  it("reload_failed : si le réessai échoue encore, l’avertissement et le bouton restent", async () => {
    client.api.admin.putCommandPermissions
      .mockResolvedValueOnce({ command: "blague", role_ids: ["400"], changed: true, reload_failed: true })
      .mockResolvedValueOnce({ command: "blague", role_ids: ["400"], changed: false, reload_failed: true })
    await renderPage()
    openHermes()
    const blague = region("/blague")
    fireEvent.change(blague.getByRole("combobox"), { target: { value: "400" } })
    fireEvent.click(blague.getByRole("button", { name: "Restreindre à ce rôle" }))
    await act(async () => {
      fireEvent.click(blague.getByRole("button", { name: "Enregistrer" }))
    })
    await act(async () => {
      fireEvent.click(blague.getByRole("button", { name: "Réessayer" }))
    })
    expect(blague.getByRole("alert").textContent).toMatch(/réessayez ou redémarrez/)
    expect(blague.getByRole("button", { name: "Réessayer" })).toBeTruthy()
  })

  it("erreur de l’API (403) : détail affiché, brouillon conservé", async () => {
    client.api.admin.putCommandPermissions.mockRejectedValue(
      new client.ApiError(403, "Le rôle « Modérateur » est au niveau du vôtre ou au-dessus : impossible de le modifier"),
    )
    await renderPage()
    openHermes()
    const blague = region("/blague")
    fireEvent.change(blague.getByRole("combobox"), { target: { value: "400" } })
    fireEvent.click(blague.getByRole("button", { name: "Restreindre à ce rôle" }))
    await act(async () => {
      fireEvent.click(blague.getByRole("button", { name: "Enregistrer" }))
    })
    expect(blague.getByRole("alert").textContent).toMatch(/au niveau du vôtre ou au-dessus/)
    expect(blague.getByRole("button", { name: "Enregistrer" })).toBeTruthy()
  })
})
