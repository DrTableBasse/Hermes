import { act, cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import type { Notification } from "@/lib/api/types"

const client = vi.hoisted(() => ({
  api: { notifications: { list: vi.fn(), markAllRead: vi.fn() } },
}))
vi.mock("@/lib/api/client", () => client)

import { NotificationBell } from "@/components/account/notification-bell"

const notif = (id: number, is_read: boolean, title = `Notif ${id}`): Notification => ({
  id,
  user_id: "100",
  type: "info",
  title,
  body: `Corps ${id}`,
  related_id: null,
  is_read,
  created_at: "2026-11-20T10:00:00Z",
})

const { list, markAllRead } = client.api.notifications

async function mount() {
  render(<NotificationBell />)
  await act(async () => {})
}

beforeEach(() => {
  list.mockResolvedValue({ notifications: [notif(1, false), notif(2, true), notif(3, false)] })
  markAllRead.mockResolvedValue({ success: true })
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe("NotificationBell", () => {
  it("compte les non-lus à partir de is_read et l'annonce dans le nom du bouton", async () => {
    await mount()
    expect(screen.getByRole("button", { name: "Notifications, 2 non lues" })).toBeTruthy()
    expect(screen.getByText("2")).toBeTruthy()
  })

  it("plafonne le compteur à 9+", async () => {
    list.mockResolvedValue({ notifications: Array.from({ length: 12 }, (_, i) => notif(i + 1, false)) })
    await mount()
    expect(screen.getByText("9+")).toBeTruthy()
  })

  it("tout lu : pas de pastille, pas de « Tout marquer lu »", async () => {
    list.mockResolvedValue({ notifications: [notif(1, true)] })
    await mount()
    expect(screen.getByRole("button", { name: "Notifications" })).toBeTruthy()
    fireEvent.click(screen.getByRole("button", { name: "Notifications" }))
    expect(screen.queryByRole("button", { name: "Tout marquer lu" })).toBeNull()
  })

  it("« Tout marquer lu » appelle markAllRead puis vide le compteur", async () => {
    await mount()
    fireEvent.click(screen.getByRole("button", { name: /^Notifications/ }))
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Tout marquer lu" }))
    })
    expect(markAllRead).toHaveBeenCalledTimes(1)
    expect(screen.getByRole("button", { name: "Notifications" })).toBeTruthy()
    expect(screen.queryByRole("button", { name: "Tout marquer lu" })).toBeNull()
  })

  it("échec de markAllRead : les non-lus restent non lus", async () => {
    markAllRead.mockRejectedValue(new Error("500"))
    await mount()
    fireEvent.click(screen.getByRole("button", { name: /^Notifications/ }))
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Tout marquer lu" }))
    })
    expect(screen.getByRole("button", { name: "Notifications, 2 non lues" })).toBeTruthy()
  })

  it("liste vide ou API indisponible : panneau « Aucune notification », rien ne casse", async () => {
    list.mockRejectedValue(new Error("503"))
    await mount()
    fireEvent.click(screen.getByRole("button", { name: "Notifications" }))
    expect(screen.getByText("Aucune notification")).toBeTruthy()
  })

  it("liste le titre et le corps, 20 notifications au plus", async () => {
    list.mockResolvedValue({ notifications: Array.from({ length: 25 }, (_, i) => notif(i + 1, true)) })
    await mount()
    fireEvent.click(screen.getByRole("button", { name: "Notifications" }))
    expect(screen.getByText("Notif 1")).toBeTruthy()
    expect(screen.getByText("Corps 1")).toBeTruthy()
    expect(screen.queryByText("Notif 21")).toBeNull()
  })
})
