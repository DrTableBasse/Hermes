import { act, cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const client = vi.hoisted(() => {
  class ApiError extends Error {
    constructor(
      readonly status: number,
      message: string,
    ) {
      super(message)
    }
  }
  return { api: { admin: { searchUsers: vi.fn() } }, ApiError }
})
vi.mock("@/lib/api/client", () => client)

import { UserSearchInput } from "@/components/admin/user-search-input"

const search = client.api.admin.searchUsers
const USERS = [
  { user_id: "1", username: "Camille", discord_avatar: null },
  { user_id: "2", username: "Camembert", discord_avatar: null },
  { user_id: "3", username: "Camion", discord_avatar: null },
]

const input = () => screen.getByRole("combobox") as HTMLInputElement
const type = (value: string) => fireEvent.change(input(), { target: { value } })
const key = (k: string) => fireEvent.keyDown(input(), { key: k })
/** Fait avancer le délai de frappe puis laisse la promesse de recherche se résoudre. */
const settle = async (ms = 300) => {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms)
  })
}

beforeEach(() => {
  vi.useFakeTimers()
  search.mockResolvedValue({ users: USERS })
})

afterEach(() => {
  cleanup()
  vi.useRealTimers()
  vi.clearAllMocks()
})

describe("UserSearchInput", () => {
  it("attend 300 ms après la dernière frappe avant d'interroger l'API (une seule requête)", async () => {
    render(<UserSearchInput selected={null} onSelect={vi.fn()} onClear={vi.fn()} />)
    type("Ca")
    await settle(200)
    type("Cam")
    await settle(299)
    expect(search).not.toHaveBeenCalled()
    await settle(1)
    expect(search).toHaveBeenCalledTimes(1)
    expect(search).toHaveBeenCalledWith("Cam")
    expect(screen.getAllByRole("option")).toHaveLength(3)
    expect(input().getAttribute("aria-expanded")).toBe("true")
  })

  it("moins de deux caractères : aucune requête, liste fermée", async () => {
    render(<UserSearchInput selected={null} onSelect={vi.fn()} onClear={vi.fn()} />)
    type("C")
    await settle(600)
    expect(search).not.toHaveBeenCalled()
    expect(screen.queryByRole("listbox")).toBeNull()
  })

  it("flèches pour parcourir, Entrée pour choisir", async () => {
    const onSelect = vi.fn()
    render(<UserSearchInput selected={null} onSelect={onSelect} onClear={vi.fn()} />)
    type("Cam")
    await settle()
    key("ArrowDown")
    key("ArrowDown")
    const active = input().getAttribute("aria-activedescendant")
    expect(active).toBeTruthy()
    expect(document.getElementById(active!)?.textContent).toContain("Camembert")
    expect(screen.getByRole("option", { name: /Camembert/ }).getAttribute("aria-selected")).toBe("true")
    key("ArrowUp")
    key("ArrowUp") // reste sur le premier
    expect(document.getElementById(input().getAttribute("aria-activedescendant")!)?.textContent).toContain("Camille")
    key("ArrowDown")
    key("Enter")
    expect(onSelect).toHaveBeenCalledWith(USERS[1])
    expect(screen.queryByRole("listbox")).toBeNull()
  })

  it("la flèche bas s'arrête sur le dernier membre ; Échap ferme sans choisir", async () => {
    const onSelect = vi.fn()
    render(<UserSearchInput selected={null} onSelect={onSelect} onClear={vi.fn()} />)
    type("Cam")
    await settle()
    for (let i = 0; i < 5; i++) key("ArrowDown")
    expect(document.getElementById(input().getAttribute("aria-activedescendant")!)?.textContent).toContain("Camion")
    key("Escape")
    expect(screen.queryByRole("listbox")).toBeNull()
    key("Enter")
    expect(onSelect).not.toHaveBeenCalled()
  })

  it("clic sur un membre : sélection", async () => {
    const onSelect = vi.fn()
    render(<UserSearchInput selected={null} onSelect={onSelect} onClear={vi.fn()} />)
    type("Cam")
    await settle()
    fireEvent.mouseDown(screen.getByRole("option", { name: /Camion/ }))
    expect(onSelect).toHaveBeenCalledWith(USERS[2])
  })

  it("aucun résultat : message, pas d'option", async () => {
    search.mockResolvedValue({ users: [] })
    render(<UserSearchInput selected={null} onSelect={vi.fn()} onClear={vi.fn()} />)
    type("Zzz")
    await settle()
    expect(screen.queryAllByRole("option")).toHaveLength(0)
    expect(screen.getByText("Aucun membre trouvé")).toBeTruthy()
  })

  it("erreur de l'API : signalée au lieu d'un faux « aucun membre »", async () => {
    search.mockRejectedValue(new client.ApiError(503, "indisponible"))
    render(<UserSearchInput selected={null} onSelect={vi.fn()} onClear={vi.fn()} />)
    type("Cam")
    await settle()
    expect(screen.getByRole("alert").textContent).toMatch(/Recherche impossible/)
    expect(screen.queryByText("Aucun membre trouvé")).toBeNull()
  })

  it("réponse périmée ignorée : seule la dernière recherche s'affiche", async () => {
    let resolveFirst: (v: unknown) => void = () => {}
    search.mockImplementationOnce(() => new Promise(r => (resolveFirst = r)))
    search.mockResolvedValueOnce({ users: [USERS[2]] })
    render(<UserSearchInput selected={null} onSelect={vi.fn()} onClear={vi.fn()} />)
    type("Cam")
    await settle()
    type("Camio")
    await settle()
    await act(async () => resolveFirst({ users: USERS }))
    expect(screen.getAllByRole("option")).toHaveLength(1)
  })

  it("membre sélectionné : pseudo affiché, bouton pour effacer", async () => {
    const onClear = vi.fn()
    render(<UserSearchInput selected={USERS[0]} onSelect={vi.fn()} onClear={onClear} />)
    expect(input().value).toBe("Camille")
    fireEvent.click(screen.getByRole("button", { name: /Effacer/ }))
    expect(onClear).toHaveBeenCalled()
  })
})
