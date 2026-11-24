import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

vi.mock("server-only", () => ({}))
vi.mock("next/headers", () => ({ cookies: async () => ({ get: () => ({ value: "tok" }) }) }))
vi.mock("next/navigation", () => ({ usePathname: () => "/admin/jeux" }))

const server = vi.hoisted(() => ({
  getSessionUser: vi.fn(),
  getAdminGames: vi.fn(),
  getDiscordRoles: vi.fn(),
  getDiscordChannels: vi.fn(),
  getAdminSettings: vi.fn(),
}))
vi.mock("@/lib/api/server", () => server)

const client = vi.hoisted(() => ({
  api: {
    admin: {
      createGame: vi.fn(),
      updateGame: vi.fn(),
      deactivateGame: vi.fn(),
      reactivateGame: vi.fn(),
      provisionGame: vi.fn(),
      gameForumsPreview: vi.fn(),
      resyncGameForums: vi.fn(),
      putSetting: vi.fn(),
      createSettingChannel: vi.fn(),
    },
    media: { upload: vi.fn() },
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

import GamesPage from "@/app/[locale]/admin/jeux/page"
import SettingsPage from "@/app/[locale]/admin/reglages/page"
import { CONFIRM_GUARD_MS } from "@/components/admin/confirm-button"
import { slugify } from "@/components/admin/game-form"
import type { AdminGame } from "@/lib/api/types"

const a = client.api.admin
const OK = { role: "ok", forum: "ok", command: "ok" } as const

const game = (over: Partial<AdminGame> & Pick<AdminGame, "key" | "name">): AdminGame => ({
  color: "#ED4245", image: null, tagline: null, discord_role_id: "100", forum_channel_id: "200", position: 1,
  active: true, emoji: "🔪", command_name: over.key, lfg_cooldown: 3600, provisioned: true, archived: false,
  status: OK, ...over,
})

const DBD = game({ key: "dbd", name: "Dead by Daylight", position: 1 })
const WAR = game({
  key: "war-dogs", name: "War Dogs", position: 2, emoji: null, command_name: null, discord_role_id: null,
  forum_channel_id: null, provisioned: false, status: null,
})
const FORTNITE = game({ key: "fortnite", name: "Fortnite", position: 3, emoji: "🏹", active: false, archived: true })
const LOL = game({ key: "lol", name: "League of Legends", position: 4, emoji: "⚔️", status: { role: "ok", forum: "missing", command: "ok" } })

const me = (permissions: string[], is_admin = false) => ({ user_id: "1", is_admin, is_redacteur: false, permissions })
const row = (name: string) => within(screen.getAllByRole("listitem").find(li => li.textContent?.includes(name))!)
const click = async (el: HTMLElement) => {
  await act(async () => {
    fireEvent.click(el)
  })
}

async function renderGames(games: AdminGame[] = [DBD, WAR, FORTNITE, LOL], bot_reachable = true) {
  server.getAdminGames.mockResolvedValue({ bot_reachable, games })
  render(await GamesPage())
}

beforeEach(() => {
  server.getSessionUser.mockResolvedValue(me(["games.manage"]))
  server.getDiscordRoles.mockResolvedValue([
    { id: "20", name: "Staff", color: 0 },
    { id: "21", name: "Modération", color: 0 },
  ])
  server.getDiscordChannels.mockResolvedValue([])
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  vi.useRealTimers()
})

describe("/admin/jeux : droits", () => {
  it("sans games.manage : page refusée, aucune liste lue", async () => {
    server.getSessionUser.mockResolvedValue(me(["settings.manage"]))
    render(await GamesPage())
    expect(screen.getByText("Zone réservée à l’administration")).toBeTruthy()
    expect(server.getAdminGames).not.toHaveBeenCalled()
    expect(screen.queryByRole("button", { name: "Ajouter un jeu" })).toBeNull()
  })

  it("games.manage suffit : liste lue avec le jeton de session", async () => {
    await renderGames()
    expect(server.getAdminGames).toHaveBeenCalledWith("tok")
    expect(screen.getByRole("button", { name: "Ajouter un jeu" })).toBeTruthy()
  })
})

describe("/admin/jeux : rattachement de rôle et de forum (C1)", () => {
  it("non-admin : listes de rôles et forums non lues, champs absents du formulaire", async () => {
    await renderGames([DBD])
    expect(server.getDiscordRoles).not.toHaveBeenCalled()
    expect(server.getDiscordChannels).not.toHaveBeenCalled()
    await click(row("Dead by Daylight").getByRole("button", { name: "Modifier" }))
    expect(row("Dead by Daylight").queryByLabelText("Rôle Discord")).toBeNull()
    expect(row("Dead by Daylight").queryByLabelText("Forum Discord")).toBeNull()
    expect(screen.getByText(/Rattacher un rôle ou un forum existant est réservé aux administrateurs/)).toBeTruthy()
    expect(screen.queryByText(/se saisissent par identifiant/)).toBeNull()
  })

  it("admin : rôle choisi dans la liste et envoyé", async () => {
    server.getSessionUser.mockResolvedValue(me(["games.manage"], true))
    a.updateGame.mockResolvedValue({ ok: true, bot_reloaded: true })
    await renderGames([DBD])
    expect(server.getDiscordRoles).toHaveBeenCalledWith("tok")
    await click(row("Dead by Daylight").getByRole("button", { name: "Modifier" }))
    fireEvent.change(row("Dead by Daylight").getByLabelText("Rôle Discord"), { target: { value: "20" } })
    await click(row("Dead by Daylight").getByRole("button", { name: "Enregistrer" }))
    expect(a.updateGame).toHaveBeenCalledWith("dbd", { discord_role_id: "20" })
  })
})

describe("/admin/jeux : statuts", () => {
  it("provisionné, non provisionné, désactivé, à recréer", async () => {
    await renderGames()
    const dbd = row("Dead by Daylight")
    expect(dbd.getByText("/dbd")).toBeTruthy()
    expect(dbd.getByText(/^rôle/).textContent).toBe("rôle ✓en place")
    expect(dbd.getByText(/^forum/).textContent).toBe("forum ✓en place")
    expect(dbd.getByText(/^commande/).textContent).toBe("commande ✓en place")
    expect(dbd.getByRole("button", { name: "Modifier" })).toBeTruthy()
    expect(dbd.getByRole("button", { name: "Désactiver" })).toBeTruthy()
    expect(dbd.queryByRole("button", { name: /Créer le rôle|Recréer/ })).toBeNull()

    const war = row("War Dogs")
    expect(war.getByText("—")).toBeTruthy()
    expect(war.getByText("Non provisionné")).toBeTruthy()
    expect(war.getByRole("button", { name: "Créer le rôle, le forum et la commande" })).toBeTruthy()

    const fortnite = row("Fortnite")
    expect(fortnite.getByText("(désactivé)")).toBeTruthy()
    expect(fortnite.getByRole("button", { name: "Réactiver" })).toBeTruthy()
    expect(fortnite.queryByRole("button", { name: "Désactiver" })).toBeNull()

    const lol = row("League of Legends")
    expect(lol.getByText("forum à recréer")).toBeTruthy()
    expect(lol.getByRole("button", { name: "Recréer ce qui manque" })).toBeTruthy()
  })

  it("forum supprimé à la main : un clic recrée, la ligne repasse au vert", async () => {
    a.provisionGame.mockResolvedValue({ role_id: "100", forum_id: "300", command: "lol", created: ["forum"], status: OK })
    await renderGames()
    await click(row("League of Legends").getByRole("button", { name: "Recréer ce qui manque" }))
    expect(a.provisionGame).toHaveBeenCalledWith("lol")
    const lol = row("League of Legends")
    expect(lol.getByRole("status").textContent).toBe(
      "« League of Legends » prêt : rôle existant réutilisé, forum créé, commande /lol disponible dans la minute.",
    )
    expect(lol.queryByText("forum à recréer")).toBeNull()
    expect(lol.queryByRole("button", { name: "Recréer ce qui manque" })).toBeNull()
  })

  it("bot muet : état inconnu annoncé, liste toujours affichée", async () => {
    await renderGames([{ ...DBD, status: null }], false)
    expect(screen.getByText(/Hermes ne répond pas : l’état Discord des jeux est inconnu/)).toBeTruthy()
    expect(row("Dead by Daylight").getByText("État Discord inconnu")).toBeTruthy()
  })
})

describe("/admin/jeux : ajout en un clic", () => {
  async function fillNewGame(name = "Apex Légendes") {
    await click(screen.getByRole("button", { name: "Ajouter un jeu" }))
    const form = within(screen.getByRole("region", { name: "Nouveau jeu" }))
    fireEvent.change(form.getByLabelText("Nom"), { target: { value: name } })
    fireEvent.change(form.getByLabelText("Émoji"), { target: { value: "🎯" } })
    fireEvent.change(form.getByLabelText("Accroche"), { target: { value: "Tombe, relève-toi." } })
    return form
  }

  it("commande et clé proposées depuis le nom ; création puis provisionnement, récapitulatif", async () => {
    a.createGame.mockResolvedValue({ ok: true, key: "apex-legendes", bot_reloaded: true })
    a.provisionGame.mockResolvedValue({
      role_id: "500", forum_id: "600", command: "apex-legendes", created: ["role", "forum"], status: OK,
    })
    await renderGames([DBD])
    const form = await fillNewGame()
    expect((form.getByLabelText("Commande") as HTMLInputElement).value).toBe("apex-legendes")
    expect((form.getByLabelText("Clé (définitive)") as HTMLInputElement).value).toBe("apex-legendes")
    await click(form.getByRole("button", { name: "Ajouter le jeu" }))

    expect(a.createGame).toHaveBeenCalledWith({
      key: "apex-legendes", name: "Apex Légendes", emoji: "🎯", color: "#9B6BFF", command_name: "apex-legendes",
      tagline: "Tombe, relève-toi.", image: null, position: 2,
    })
    expect(a.provisionGame).toHaveBeenCalledWith("apex-legendes")
    expect(a.createGame.mock.invocationCallOrder[0]).toBeLessThan(a.provisionGame.mock.invocationCallOrder[0])
    expect(screen.queryByRole("region", { name: "Nouveau jeu" })).toBeNull()
    const apex = row("Apex Légendes")
    expect(apex.getByRole("status").textContent).toBe(
      "« Apex Légendes » prêt : rôle créé, forum créé, commande /apex-legendes disponible dans la minute.",
    )
    expect(apex.getByText("/apex-legendes")).toBeTruthy()
    expect(apex.queryByText("Non provisionné")).toBeNull()
  })

  it("commande saisie à la main : le nom ne l’écrase plus", async () => {
    await renderGames([])
    const form = await fillNewGame("Apex")
    fireEvent.change(form.getByLabelText("Commande"), { target: { value: "/APEX_1" } })
    fireEvent.change(form.getByLabelText("Nom"), { target: { value: "Apex Legends" } })
    expect((form.getByLabelText("Commande") as HTMLInputElement).value).toBe("apex_1")
    expect((form.getByLabelText("Clé (définitive)") as HTMLInputElement).value).toBe("apex-legends")
  })

  it("commande mal formée ou émoji vide : envoi bloqué côté navigateur", async () => {
    await renderGames([])
    const form = await fillNewGame("Apex")
    fireEvent.change(form.getByLabelText("Commande"), { target: { value: "apex legends" } })
    expect(form.getByText(/Commande : minuscules/)).toBeTruthy()
    expect((form.getByRole("button", { name: "Ajouter le jeu" }) as HTMLButtonElement).disabled).toBe(true)
    fireEvent.change(form.getByLabelText("Commande"), { target: { value: "apex" } })
    fireEvent.change(form.getByLabelText("Émoji"), { target: { value: " " } })
    expect(form.getByText(/Émoji requis/)).toBeTruthy()
    expect((form.getByRole("button", { name: "Ajouter le jeu" }) as HTMLButtonElement).disabled).toBe(true)
  })

  it.each([
    ["La commande /rang existe déjà."],
    ["L'émoji 🔪 est déjà utilisé."],
    ["Émoji invalide : un seul émoji attendu (Unicode ou personnalisé <:nom:id>)."],
  ])("422 « %s » : affiché dans le formulaire, saisie gardée, rien provisionné", async detail => {
    a.createGame.mockRejectedValue(new client.ApiError(422, detail))
    await renderGames([DBD])
    const form = await fillNewGame()
    await click(form.getByRole("button", { name: "Ajouter le jeu" }))
    expect(form.getByRole("alert").textContent).toBe(`Refusé : ${detail.replace(/\.$/, "")}.`)
    expect((form.getByLabelText("Nom") as HTMLInputElement).value).toBe("Apex Légendes")
    expect(a.provisionGame).not.toHaveBeenCalled()
    expect(screen.getAllByRole("listitem")).toHaveLength(1)
  })

  it("provisionnement refusé par Discord : jeu créé, non provisionné, erreur et bouton pour réessayer", async () => {
    a.createGame.mockResolvedValue({ ok: true, key: "apex-legendes", bot_reloaded: true })
    a.provisionGame.mockRejectedValue(
      new client.ApiError(403, "Permission refusée — le bot n'a pas les droits nécessaires (Gérer les rôles, Gérer les salons)"),
    )
    await renderGames([DBD])
    const form = await fillNewGame()
    await click(form.getByRole("button", { name: "Ajouter le jeu" }))
    const apex = row("Apex Légendes")
    expect(apex.getByRole("alert").textContent).toMatch(/^Permission refusée — le bot n'a pas les droits/)
    expect(apex.getByText("Non provisionné")).toBeTruthy()
    a.provisionGame.mockResolvedValue({ role_id: "5", forum_id: "6", command: "apex-legendes", created: [], status: OK })
    await click(apex.getByRole("button", { name: "Créer le rôle, le forum et la commande" }))
    expect(row("Apex Légendes").getByRole("status").textContent).toMatch(/rôle existant réutilisé, forum existant réutilisé/)
  })

  it("délai dépassé (504 du bot) : le détail de l’API est affiché tel quel", async () => {
    const detail = "Le bot n'a pas répondu à temps : l'action se termine peut-être encore. Rechargez la page pour voir l'état du jeu."
    a.provisionGame.mockRejectedValue(new client.ApiError(504, detail))
    await renderGames([WAR])
    await click(row("War Dogs").getByRole("button", { name: "Créer le rôle, le forum et la commande" }))
    expect(row("War Dogs").getByRole("alert").textContent).toBe(detail)
  })

  it("action longue : « en cours… » sur la ligne, le reste de la page reste utilisable", async () => {
    let finish!: (value: unknown) => void
    a.provisionGame.mockReturnValue(new Promise(resolve => (finish = resolve)))
    await renderGames([DBD, WAR])
    await click(row("War Dogs").getByRole("button", { name: "Créer le rôle, le forum et la commande" }))
    const war = row("War Dogs")
    expect(war.getByRole("status").textContent).toMatch(/en cours…/)
    expect((war.getByRole("button", { name: "Créer le rôle, le forum et la commande" }) as HTMLButtonElement).disabled).toBe(true)
    expect(screen.getAllByRole("listitem")[1].getAttribute("aria-busy")).toBe("true")
    // Les autres jeux et l'ajout ne sont pas bloqués.
    expect((row("Dead by Daylight").getByRole("button", { name: "Modifier" }) as HTMLButtonElement).disabled).toBe(false)
    expect((screen.getByRole("button", { name: "Ajouter un jeu" }) as HTMLButtonElement).disabled).toBe(false)
    await act(async () => finish({ role_id: "1", forum_id: "2", command: "war-dogs", created: ["role", "forum"], status: OK }))
    expect(row("War Dogs").getByRole("status").textContent).toMatch(/prêt : rôle créé, forum créé/)
  })
})

describe("/admin/jeux : modifier, désactiver, réactiver", () => {
  it("modifier n’envoie que les champs changés", async () => {
    a.updateGame.mockResolvedValue({ ok: true, bot_reloaded: true })
    await renderGames([DBD])
    await click(row("Dead by Daylight").getByRole("button", { name: "Modifier" }))
    fireEvent.change(row("Dead by Daylight").getByLabelText("Émoji"), { target: { value: "🗡️" } })
    await click(row("Dead by Daylight").getByRole("button", { name: "Enregistrer" }))
    expect(a.updateGame).toHaveBeenCalledWith("dbd", { emoji: "🗡️" })
    expect(row("Dead by Daylight").getByRole("status").textContent).toBe("« Dead by Daylight » enregistré.")
  })

  it("modification refusée (422) : formulaire gardé ouvert, erreur sur la ligne", async () => {
    a.updateGame.mockRejectedValue(new client.ApiError(422, "La commande /blague existe déjà."))
    await renderGames([DBD])
    await click(row("Dead by Daylight").getByRole("button", { name: "Modifier" }))
    fireEvent.change(row("Dead by Daylight").getByLabelText("Commande"), { target: { value: "blague" } })
    await click(row("Dead by Daylight").getByRole("button", { name: "Enregistrer" }))
    expect(a.updateGame).toHaveBeenCalledWith("dbd", { command_name: "blague" })
    expect(row("Dead by Daylight").getByRole("alert").textContent).toBe("Refusé : La commande /blague existe déjà.")
    expect(row("Dead by Daylight").getByLabelText("Commande")).toBeTruthy()
  })

  it("désactiver demande confirmation ; Annuler n’appelle rien ; confirmé → archivé ; réactiver rétablit", async () => {
    a.deactivateGame.mockResolvedValue({ ok: true, status: { role: "ok", forum: "ok", command: "none" } })
    a.reactivateGame.mockResolvedValue({ ok: true, status: OK })
    await renderGames([DBD])
    fireEvent.click(row("Dead by Daylight").getByRole("button", { name: "Désactiver" }))
    const ask = within(screen.getByRole("group", { name: /^Désactiver « Dead by Daylight » \?/ }))
    fireEvent.click(ask.getByRole("button", { name: "Annuler" }))
    expect(a.deactivateGame).not.toHaveBeenCalled()

    vi.useFakeTimers({ toFake: ["Date"] })
    fireEvent.click(row("Dead by Daylight").getByRole("button", { name: "Désactiver" }))
    vi.setSystemTime(Date.now() + CONFIRM_GUARD_MS)
    const group = within(screen.getByRole("group", { name: /Commande retirée, forum archivé, rôle gardé/ }))
    await click(group.getByRole("button", { name: "Désactiver" }))
    vi.useRealTimers()
    expect(a.deactivateGame).toHaveBeenCalledWith("dbd")
    const dbd = row("Dead by Daylight")
    expect(dbd.getByText("(désactivé)")).toBeTruthy()
    expect(dbd.getByRole("status").textContent).toMatch(/désactivé : commande retirée, forum archivé, rôle gardé/)

    await click(dbd.getByRole("button", { name: "Réactiver" }))
    expect(a.reactivateGame).toHaveBeenCalledWith("dbd")
    expect(row("Dead by Daylight").queryByText("(désactivé)")).toBeNull()
    expect(row("Dead by Daylight").getByRole("status").textContent).toMatch(/réactivé/)
  })

  it("désactivation refusée par Discord : erreur traduite, jeu toujours actif", async () => {
    a.deactivateGame.mockRejectedValue(new client.ApiError(502, "Erreur Discord : Missing Access"))
    await renderGames([DBD])
    vi.useFakeTimers({ toFake: ["Date"] })
    fireEvent.click(row("Dead by Daylight").getByRole("button", { name: "Désactiver" }))
    vi.setSystemTime(Date.now() + CONFIRM_GUARD_MS)
    await click(within(screen.getByRole("group", { name: /\?/ })).getByRole("button", { name: "Désactiver" }))
    vi.useRealTimers()
    expect(row("Dead by Daylight").getByRole("alert").textContent).toBe("Erreur Discord : Missing Access")
    expect(row("Dead by Daylight").queryByText("(désactivé)")).toBeNull()
  })
})

describe("Réglages : rôles du staff", () => {
  const STAFF = {
    key: "staff_roles", label: "Rôles du staff", kind: "text", value: "20", can_create: false, admin_only: true, resolved: null,
  }

  async function renderSettings(isAdmin: boolean) {
    server.getSessionUser.mockResolvedValue(me(["settings.manage", "games.manage"], isAdmin))
    server.getAdminSettings.mockResolvedValue({ groups: [{ name: "Rôles", items: [STAFF] }] })
    render(await SettingsPage())
  }

  it("non-admin : valeur affichée par nom, ni saisie ni mise à jour des forums", async () => {
    await renderSettings(false)
    expect(screen.getByText("@Staff", { selector: "span" })).toBeTruthy()
    expect(screen.getByText(/Réservé aux administrateurs/)).toBeTruthy()
    expect(screen.queryByRole("checkbox")).toBeNull()
    expect(screen.queryByRole("button", { name: "Mettre à jour les forums" })).toBeNull()
  })

  it("admin : sélection multiple de rôles enregistrée par identifiants", async () => {
    client.api.admin.putSetting.mockResolvedValue({ key: "staff_roles", value: "20,21", bot_reloaded: true })
    await renderSettings(true)
    const group = within(screen.getByRole("group", { name: "Rôles du staff" }))
    expect((group.getByRole("checkbox", { name: "@Staff" }) as HTMLInputElement).checked).toBe(true)
    const save = screen.getByRole("button", { name: "Enregistrer" }) as HTMLButtonElement
    expect(save.disabled).toBe(true)
    fireEvent.click(group.getByRole("checkbox", { name: "@Modération" }))
    await click(save)
    expect(a.putSetting).toHaveBeenCalledWith("staff_roles", "20,21")
    expect(screen.getByText("@Staff, @Modération", { selector: "span" })).toBeTruthy()
  })

  const PREVIEW = {
    forums: 2,
    details: [
      {
        key: "lol", game: "League of Legends", forum_id: "201", forum: "lol", changes: [
          { target: "Invité", kind: "role", change: "removed", before: { allow: ["view_channel"], deny: [] }, after: null },
          {
            target: "League of Legends", kind: "role", change: "modified",
            before: { allow: ["view_channel"], deny: [] },
            after: { allow: ["send_messages", "view_channel"], deny: [] },
          },
          { target: "Staff", kind: "role", change: "added", before: null, after: { allow: ["view_channel"], deny: [] } },
        ],
      },
      { key: "dbd", game: "Dead by Daylight", forum_id: "200", forum: "dbd", changes: [] },
    ],
  }

  it("aperçu : chaque forum et, pour chacun, les surcharges retirées ou modifiées (avant → après)", async () => {
    a.gameForumsPreview.mockResolvedValue(PREVIEW)
    await renderSettings(true)
    await click(screen.getByRole("button", { name: "Mettre à jour les forums" }))
    const ask = within(screen.getByRole("group", { name: "Confirmer la mise à jour des forums" }))
    expect(ask.getByText("Réécrire les permissions de 2 forums de jeux ?")).toBeTruthy()
    const lol = within(ask.getByRole("listitem", { name: "#lol (League of Legends)" }))
    expect(lol.getByText("@Invité : surcharge retirée (voir le salon → aucune)")).toBeTruthy()
    expect(lol.getByText("@League of Legends : surcharge modifiée (voir le salon → écrire, voir le salon)")).toBeTruthy()
    expect(lol.getByText("@Staff : surcharge ajoutée (aucune → voir le salon)")).toBeTruthy()
    expect(within(ask.getByRole("listitem", { name: "#dbd (Dead by Daylight)" })).getByText("Déjà à jour.")).toBeTruthy()
    expect(a.resyncGameForums).not.toHaveBeenCalled()
  })

  it("réécriture partielle : forums en échec signalés", async () => {
    a.gameForumsPreview.mockResolvedValue(PREVIEW)
    a.resyncGameForums.mockResolvedValue({ ok: false, forums: 1, failed: [{ key: "lol", forum: "lol", error: "permission refusée" }] })
    await renderSettings(true)
    await click(screen.getByRole("button", { name: "Mettre à jour les forums" }))
    await click(screen.getByRole("button", { name: "Confirmer" }))
    expect(screen.getByRole("alert").textContent).toBe(
      "Permissions réécrites : 1 forum de jeux. Échec pour #lol (permission refusée) : relance pour réessayer.",
    )
  })

  it("liste du staff modifiée non enregistrée : mise à jour des forums bloquée", async () => {
    await renderSettings(true)
    const group = within(screen.getByRole("group", { name: "Rôles du staff" }))
    fireEvent.click(group.getByRole("checkbox", { name: "@Modération" }))
    expect((screen.getByRole("button", { name: "Mettre à jour les forums" }) as HTMLButtonElement).disabled).toBe(true)
    expect(screen.getByText(/Enregistre d’abord la nouvelle liste/)).toBeTruthy()
    fireEvent.click(group.getByRole("checkbox", { name: "@Modération" }))
    expect((screen.getByRole("button", { name: "Mettre à jour les forums" }) as HTMLButtonElement).disabled).toBe(false)
  })

  it("mettre à jour les forums : aperçu du nombre, confirmation de ce nombre, résultat", async () => {
    a.gameForumsPreview.mockResolvedValue({ forums: 6, details: [] })
    a.resyncGameForums.mockResolvedValue({ ok: true, forums: 6, failed: [] })
    await renderSettings(true)
    await click(screen.getByRole("button", { name: "Mettre à jour les forums" }))
    expect(a.resyncGameForums).not.toHaveBeenCalled()
    const ask = within(screen.getByRole("group", { name: "Confirmer la mise à jour des forums" }))
    expect(ask.getByText("Réécrire les permissions de 6 forums de jeux ?")).toBeTruthy()
    await click(ask.getByRole("button", { name: "Confirmer" }))
    expect(a.resyncGameForums).toHaveBeenCalledWith(6)
    expect(screen.getByText("Permissions réécrites : 6 forums de jeux.")).toBeTruthy()
  })

  it("nombre changé entre l’aperçu et la confirmation (409) : message de l’API", async () => {
    a.gameForumsPreview.mockResolvedValue({ forums: 6, details: [] })
    a.resyncGameForums.mockRejectedValue(
      new client.ApiError(409, "Le nombre a changé : 5 forum(s) de jeux concerné(s). Vérifiez puis confirmez à nouveau."),
    )
    await renderSettings(true)
    await click(screen.getByRole("button", { name: "Mettre à jour les forums" }))
    await click(screen.getByRole("button", { name: "Confirmer" }))
    expect(screen.getByRole("alert").textContent).toMatch(/^Refusé : Le nombre a changé : 5 forum\(s\)/)
    expect(screen.getByRole("button", { name: "Mettre à jour les forums" })).toBeTruthy()
  })
})

describe("slugify", () => {
  it("accents retirés, séparateurs en tirets, 32 caractères au plus", () => {
    expect(slugify("Apex Légendes !")).toBe("apex-legendes")
    expect(slugify("  Œuvre—Été  ")).toBe("uvre-ete")
    expect(slugify("a".repeat(40))).toHaveLength(32)
    expect(slugify(`${"a".repeat(31)} b`)).toBe("a".repeat(31))
  })
})
