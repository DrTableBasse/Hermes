import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import type { AuditEvent, AuditPage } from "@/lib/api/types"

const nav = vi.hoisted(() => ({ params: new URLSearchParams() }))
vi.mock("next/navigation", () => ({ useSearchParams: () => nav.params }))

const admin = vi.hoisted(() => ({ audit: vi.fn(), auditFacets: vi.fn() }))
vi.mock("@/lib/api/client", async importOriginal => {
  const real = await importOriginal<typeof import("@/lib/api/client")>()
  return { ...real, api: { admin } }
})

import { AuditJournal } from "@/components/admin/audit-journal"
import { ApiError } from "@/lib/api/client"

const event = (over: Partial<AuditEvent>): AuditEvent => ({
  id: 1,
  occurred_at: "2026-11-23T10:00:00+00:00",
  kind: "command",
  action: "/fortnite",
  source: "hermes",
  actor_id: "279205522970902528",
  actor_name: "Kéfir",
  target_id: null,
  target_name: null,
  channel_id: "5",
  channel_name: "général",
  success: true,
  details: {},
  ...over,
})

const page = (events: AuditEvent[], over: Partial<AuditPage> = {}): AuditPage => ({
  events,
  total: events.length,
  page: 1,
  pages: 1,
  ...over,
})

async function mount(props: Partial<Parameters<typeof AuditJournal>[0]> = {}) {
  await act(async () => {
    render(<AuditJournal onInspect={() => {}} inspectorId="fiche" {...props} />)
  })
}

/** Dernier appel à `api.admin.audit` : (filtres, page). */
const lastCall = () => admin.audit.mock.calls.at(-1)

beforeEach(() => {
  nav.params = new URLSearchParams()
  window.history.replaceState(null, "", "/admin/moderation")
  admin.audit.mockResolvedValue(page([]))
  admin.auditFacets.mockResolvedValue({ kinds: {}, channels: [] })
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe("AuditJournal", () => {
  it("affiche les lignes, l'échec et le lien CSV filtré", async () => {
    nav.params = new URLSearchParams("type=command,sanction")
    admin.audit.mockResolvedValue(
      page([
        event({ id: 1, details: { options: { mode: "solo" } } }),
        event({ id: 2, kind: "sanction", action: "ban", source: "site", success: false, target_id: "42", target_name: "Troll", details: { reason: "spam" } }),
      ]),
    )
    await mount()
    expect(lastCall()).toEqual([{ kind: ["command", "sanction"] }, 1])
    const table = screen.getByRole("table")
    const rows = within(table).getAllByRole("row").slice(1)
    expect(rows).toHaveLength(2)
    expect(within(rows[0]).getByText("Commande")).toBeTruthy()
    expect(within(rows[0]).getByText("/fortnite")).toBeTruthy()
    expect(within(rows[0]).queryByText("échec")).toBeNull()
    expect(within(rows[1]).getByText("échec")).toBeTruthy()
    expect(within(rows[1]).getByText("bannissement")).toBeTruthy()
    // Heure de Paris (UTC+1 en novembre).
    expect(within(rows[0]).getByText(/23\/11\/2026.*11:00/)).toBeTruthy()
    // Détail : options de commande et raison en paires lisibles.
    expect(within(rows[0]).getByText("Option « mode »")).toBeTruthy()
    expect(within(rows[1]).getByText("Raison")).toBeTruthy()
    expect(within(rows[1]).getByText("spam")).toBeTruthy()
    const csv = screen.getByRole("link", { name: "Exporter CSV" })
    expect(csv.getAttribute("href")).toBe("/api/proxy/admin/audit.csv?kind=command%2Csanction")
  })

  it("auteur et cible ouvrent la fiche du membre", async () => {
    const onInspect = vi.fn()
    admin.audit.mockResolvedValue(page([event({ target_id: "42", target_name: "Troll" })]))
    await mount({ onInspect })
    const author = screen.getByRole("link", { name: "Kéfir" })
    expect(author.getAttribute("href")).toBe("#fiche")
    fireEvent.click(author)
    expect(onInspect).toHaveBeenCalledWith({ user_id: "279205522970902528", username: "Kéfir", discord_avatar: null })
    fireEvent.click(screen.getByRole("link", { name: "Troll" }))
    expect(onInspect).toHaveBeenLastCalledWith({ user_id: "42", username: "Troll", discord_avatar: null })
  })

  it("vocal modéré sans auteur : « — » et libellé selon details.active", async () => {
    admin.audit.mockResolvedValue(
      page([event({ kind: "voice", action: "server_mute", source: "discord", actor_id: null, actor_name: null, target_id: "42", target_name: "Troll", details: { active: true } })]),
    )
    await mount()
    const row = within(screen.getByRole("table")).getAllByRole("row")[1]
    expect(within(row).getByText("micro coupé par la modération")).toBeTruthy()
    expect(within(row).getAllByRole("cell")[3].textContent).toBe("—")
  })

  it("changer un filtre recharge la page 1", async () => {
    admin.audit.mockResolvedValue(page([event({})], { pages: 3, total: 120 }))
    await mount()
    expect(screen.getByText("Page 1 / 3")).toBeTruthy()
    admin.audit.mockResolvedValue(page([event({})], { page: 2, pages: 3, total: 120 }))
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Suivant" })))
    expect(lastCall()).toEqual([{}, 2])
    expect(screen.getByText("Page 2 / 3")).toBeTruthy()
    expect(window.location.search).toBe("?page=2")
    await act(async () => fireEvent.change(screen.getByLabelText("Source"), { target: { value: "discord" } }))
    expect(lastCall()).toEqual([{ source: ["discord"] }, 1])
    expect(window.location.search).toBe("?source=discord")
    // Champ texte : appliqué à la validation du formulaire, page 1 aussi.
    await act(async () => fireEvent.change(screen.getByLabelText("Auteur"), { target: { value: "Kéfir" } }))
    expect(lastCall()).toEqual([{ source: ["discord"] }, 1])
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Appliquer" })))
    expect(lastCall()).toEqual([{ source: ["discord"], actor: "Kéfir" }, 1])
    await act(async () => fireEvent.click(screen.getByLabelText("Échecs seulement")))
    expect(lastCall()).toEqual([{ source: ["discord"], actor: "Kéfir", failedOnly: true }, 1])
    expect(screen.getByRole("link", { name: "Exporter CSV" }).getAttribute("href")).toBe(
      "/api/proxy/admin/audit.csv?source=discord&actor=K%C3%A9fir&success=false",
    )
  })

  it("le menu Action ne propose que les actions du type choisi", async () => {
    admin.auditFacets.mockResolvedValue({ kinds: { voice: ["join", "leave"], message: ["edit"] }, channels: [] })
    await mount()
    const action = screen.getByLabelText("Action") as HTMLSelectElement
    expect(action.disabled).toBe(true)
    await act(async () => fireEvent.change(screen.getByLabelText("Type"), { target: { value: "voice" } }))
    expect(action.disabled).toBe(false)
    const labels = Array.from(action.options).map(o => o.textContent)
    expect(labels).toEqual(["Toutes", "arrivée", "départ"])
    await act(async () => fireEvent.change(action, { target: { value: "leave" } }))
    expect(lastCall()).toEqual([{ kind: ["voice"], action: ["leave"] }, 1])
    // Changer de type réinitialise l'action.
    await act(async () => fireEvent.change(screen.getByLabelText("Type"), { target: { value: "message" } }))
    expect(lastCall()).toEqual([{ kind: ["message"] }, 1])
    expect(Array.from(action.options).map(o => o.textContent)).toEqual(["Toutes", "modifié"])
  })

  it("le raccourci « Messages » pose type=message", async () => {
    await mount()
    const shortcut = screen.getByRole("button", { name: "Messages" })
    expect(shortcut.getAttribute("aria-pressed")).toBe("false")
    await act(async () => fireEvent.click(shortcut))
    expect(lastCall()).toEqual([{ kind: ["message"] }, 1])
    expect(window.location.search).toBe("?type=message")
    expect(shortcut.getAttribute("aria-pressed")).toBe("true")
    expect((screen.getByLabelText("Type") as HTMLSelectElement).value).toBe("message")
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Tout" })))
    expect(lastCall()).toEqual([{}, 1])
    expect(window.location.search).toBe("")
  })

  it("salon : menu rempli par les facettes", async () => {
    admin.auditFacets.mockResolvedValue({ kinds: {}, channels: [{ id: "5", name: "général" }] })
    await mount()
    await act(async () => fireEvent.change(screen.getByLabelText("Salon"), { target: { value: "5" } }))
    expect(lastCall()).toEqual([{ channelId: "5" }, 1])
    expect(window.location.search).toBe("?salon=5")
  })

  it("API en erreur : message, pas de tableau", async () => {
    admin.audit.mockRejectedValue(new ApiError(403, "Admin requis"))
    await mount()
    expect(screen.getByRole("alert").textContent).toBe("Action réservée à l’administration.")
    expect(screen.queryByRole("table")).toBeNull()
  })

  it("aucun évènement : message, pas de tableau", async () => {
    await mount()
    expect(screen.getByText("Aucun évènement pour ces filtres.")).toBeTruthy()
    expect(screen.queryByRole("table")).toBeNull()
  })
})
