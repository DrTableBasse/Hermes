import { act, cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"
import type { DiscordChannel, DiscordRole, SettingItem } from "@/lib/api/types"

const client = vi.hoisted(() => {
  class ApiError extends Error {
    constructor(
      readonly status: number,
      message: string,
    ) {
      super(message)
    }
  }
  return { api: { admin: { putSetting: vi.fn(), createSettingChannel: vi.fn() } }, ApiError }
})
vi.mock("@/lib/api/client", () => client)

import { SettingField, validateSetting } from "@/components/admin/setting-field"
import { SettingsPanel } from "@/components/admin/settings-panel"

const { putSetting, createSettingChannel } = client.api.admin

const CHANNELS: DiscordChannel[] = [
  { id: "10", name: "Général", type: "category", category: null },
  { id: "11", name: "accueil", type: "text", category: "Général" },
  { id: "12", name: "vocal", type: "voice", category: "Général" },
  { id: "13", name: "jeux", type: "forum", category: null },
]
const ROLES: DiscordRole[] = [{ id: "20", name: "Modération", color: 0 }]

const setting = (over: Partial<SettingItem>): SettingItem => ({
  key: "welcome_channel",
  label: "Salon d’accueil",
  kind: "channel",
  value: "",
  can_create: true,
  admin_only: false,
  resolved: null,
  ...over,
})

const renderField = (item: SettingItem, channels: DiscordChannel[] | null = CHANNELS, roles: DiscordRole[] | null = ROLES) =>
  render(<SettingField item={item} channels={channels} roles={roles} onChannelCreated={vi.fn()} />)

const click = async (name: string | RegExp) => {
  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name }))
  })
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe("SettingField", () => {
  it("salon : liste alimentée par /admin/discord (textes et forums, pas le vocal), valeur affichée par son nom", () => {
    renderField(setting({ value: "11", resolved: { id: "11", name: "accueil", exists: true } }))
    expect(screen.getByText("#accueil", { selector: "span" })).toBeTruthy()
    const options = [...(screen.getByLabelText("Salon d’accueil") as HTMLSelectElement).options].map(o => o.textContent)
    expect(options).toEqual(["— Non réglé —", "#accueil", "#jeux"])
    expect(screen.queryByRole("button", { name: "Créer le salon" })).toBeNull()
  })

  it("salon introuvable : signalé, bouton « Créer le salon » ; création → enregistré", async () => {
    createSettingChannel.mockResolvedValue({ id: "99", name: "accueil" })
    const onCreated = vi.fn()
    render(
      <SettingField
        item={setting({ value: "55", resolved: { id: "55", name: null, exists: false } })}
        channels={CHANNELS}
        roles={ROLES}
        onChannelCreated={onCreated}
      />,
    )
    expect(screen.getByText("Introuvable")).toBeTruthy()
    expect(screen.getByText(/introuvable sur Discord \(identifiant 55\)/)).toBeTruthy()
    await click("Créer le salon")
    expect(createSettingChannel).toHaveBeenCalledWith("welcome_channel")
    expect(onCreated).toHaveBeenCalledWith(expect.objectContaining({ id: "99", name: "accueil" }))
    expect(screen.getByRole("status").textContent).toMatch(/Enregistré/)
  })

  it("enregistre la valeur choisie et confirme « Enregistré »", async () => {
    putSetting.mockResolvedValue({ key: "welcome_channel", value: "11", bot_reloaded: true })
    renderField(setting({}))
    fireEvent.change(screen.getByLabelText("Salon d’accueil"), { target: { value: "11" } })
    await click("Enregistrer")
    expect(putSetting).toHaveBeenCalledWith("welcome_channel", "11")
    expect(screen.getByRole("status").textContent).toBe("Enregistré.")
    expect(screen.getByText("#accueil", { selector: "span" })).toBeTruthy()
  })

  it("Effacer envoie une valeur vide : le défaut s’applique", async () => {
    putSetting.mockResolvedValue({ key: "voice_hours_for_role", value: "", bot_reloaded: false })
    renderField(setting({ key: "voice_hours_for_role", label: "Heures", kind: "int", value: "50", can_create: false }))
    await click("Effacer")
    expect(putSetting).toHaveBeenCalledWith("voice_hours_for_role", "")
    expect(screen.getByRole("status").textContent).toMatch(/valeur par défaut.*sous 5 minutes/)
  })

  it("422 de l’API affiché près du champ (aria-describedby)", async () => {
    putSetting.mockRejectedValue(new client.ApiError(422, "URL http(s) attendue"))
    renderField(setting({ key: "invite_url", label: "Lien d’invitation", kind: "url", can_create: false }))
    const input = screen.getByLabelText("Lien d’invitation")
    fireEvent.change(input, { target: { value: "https://discord.gg/x" } })
    await click("Enregistrer")
    const alert = screen.getByRole("alert")
    expect(alert.textContent).toBe("Refusé : URL http(s) attendue.")
    expect(document.getElementById(input.getAttribute("aria-describedby")!)?.contains(alert)).toBe(true)
  })

  it("saisie invalide : message et envoi bloqué", () => {
    renderField(setting({ key: "bump_role_threshold", label: "Bumps", kind: "int", can_create: false }))
    fireEvent.change(screen.getByLabelText("Bumps"), { target: { value: "-3" } })
    expect(screen.getByText("Nombre entier positif attendu.")).toBeTruthy()
    expect((screen.getByRole("button", { name: "Enregistrer" }) as HTMLButtonElement).disabled).toBe(true)
  })

  it("rôle par nom par défaut (« Modération ») : affiché sans erreur, à choisir dans la liste", () => {
    renderField(setting({ key: "mod_role", label: "Rôle modération", kind: "role", value: "Modération", can_create: false }))
    expect(screen.getByText(/« Modération » \(nom par défaut/, { selector: "span" })).toBeTruthy()
    expect(screen.queryByText(/numérique attendu/)).toBeNull()
    const options = [...(screen.getByLabelText("Rôle modération") as HTMLSelectElement).options].map(o => o.textContent)
    expect(options).toContain("@Modération")
  })

  it("bot muet : saisie d’identifiant à la place de la liste", () => {
    renderField(setting({ value: "11", resolved: { id: "11", name: null, exists: null } }), null, null)
    expect(screen.getByLabelText("Salon d’accueil").tagName).toBe("INPUT")
    expect(screen.getByText(/saisis l’identifiant/)).toBeTruthy()
    expect(screen.queryByText("Introuvable")).toBeNull()
  })

  it("validateSetting suit le registre", () => {
    expect(validateSetting({ key: "x", kind: "url" }, "ftp://a")).toMatch(/http/)
    expect(validateSetting({ key: "x", kind: "bool" }, "TRUE")).toBeNull()
    expect(validateSetting({ key: "authorized_roles", kind: "text" }, "1, 2")).toBeNull()
    expect(validateSetting({ key: "authorized_roles", kind: "text" }, "1;2")).toMatch(/virgules/)
    expect(validateSetting({ key: "x", kind: "channel" }, "")).toBeNull()
  })
})

describe("SettingsPanel", () => {
  it("réglages importants marqués, ancre par réglage", () => {
    render(
      <SettingsPanel
        groups={[{ name: "Site", items: [setting({ key: "invite_url", label: "Lien", kind: "url", can_create: false })] }]}
        channels={CHANNELS}
        roles={ROLES}
        isAdmin
      />,
    )
    expect(screen.getByText("Important")).toBeTruthy()
    expect(document.getElementById("setting-invite_url")).toBeTruthy()
  })
})
