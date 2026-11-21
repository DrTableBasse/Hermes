import { act, cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import type { Game } from "@/lib/api/types"

const client = vi.hoisted(() => {
  class ApiError extends Error {
    constructor(
      readonly status: number,
      message: string,
    ) {
      super(message)
    }
  }
  return { api: { staff: { updateMyProfile: vi.fn() } }, ApiError }
})
vi.mock("@/lib/api/client", () => client)

import { StaffProfileForm } from "@/components/staff/staff-profile-form"

const game = (key: string, name: string): Game => ({
  key,
  name,
  color: "#3FA9C9",
  image: null,
  tagline: null,
  players: null,
  forum_url: null,
})

const GAMES = [
  game("dbd", "Dead by Daylight"),
  game("wardogs", "War Dogs"),
  game("lol", "League of Legends"),
  game("warframe", "Warframe"),
  game("overwatch", "Overwatch"),
  game("fortnite", "Fortnite"),
  game("minecraft", "Minecraft"),
]

const update = client.api.staff.updateMyProfile

const motto = () => screen.getByLabelText("Ta phrase") as HTMLTextAreaElement
const submit = () => screen.getByRole("button", { name: "Enregistrer" })
const tick = (name: string) => fireEvent.click(screen.getByRole("checkbox", { name }))
const send = async () => {
  await act(async () => {
    fireEvent.click(submit())
  })
}

beforeEach(() => {
  update.mockResolvedValue({ ok: true })
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe("StaffProfileForm", () => {
  it("bloque l'envoi au-delà de 140 caractères", async () => {
    render(<StaffProfileForm motto={null} selected={[]} games={GAMES} />)
    fireEvent.change(motto(), { target: { value: "a".repeat(141) } })
    expect(screen.getByText("141 / 140")).toBeTruthy()
    expect(screen.getByText(/140 caractères maximum/)).toBeTruthy()
    await send()
    expect(update).not.toHaveBeenCalled()

    fireEvent.change(motto(), { target: { value: "a".repeat(140) } })
    await send()
    expect(update).toHaveBeenCalledWith({ motto: "a".repeat(140), games: [] })
  })

  it("compte les caractères comme l'API (un emoji = un caractère)", async () => {
    render(<StaffProfileForm motto={null} selected={[]} games={GAMES} />)
    fireEvent.change(motto(), { target: { value: "🌭".repeat(140) } })
    expect(screen.getByText("140 / 140")).toBeTruthy()
    await send()
    expect(update).toHaveBeenCalledTimes(1)
  })

  it("bloque l'envoi au-delà de 5 jeux", async () => {
    render(<StaffProfileForm motto="Salut" selected={["dbd", "wardogs", "lol", "warframe", "overwatch"]} games={GAMES} />)
    tick("Fortnite")
    expect(screen.getByText(/5 jeux maximum/)).toBeTruthy()
    await send()
    expect(update).not.toHaveBeenCalled()

    tick("Dead by Daylight")
    await send()
    expect(update).toHaveBeenCalledWith({ motto: "Salut", games: ["wardogs", "lol", "warframe", "overwatch", "fortnite"] })
  })

  it("une phrase tient sur une ligne : les retours à la ligne collés deviennent des espaces", async () => {
    render(<StaffProfileForm motto={null} selected={[]} games={GAMES} />)
    const lineSeparator = String.fromCharCode(0x2028)
    fireEvent.change(motto(), { target: { value: `Je veille\r\nsur le vocal${lineSeparator}de 22 h à 3 h` } })
    expect(motto().value).toBe("Je veille sur le vocal de 22 h à 3 h")
  })

  it("phrase vide → null ; succès annoncé", async () => {
    render(<StaffProfileForm motto="Ancienne" selected={["lol"]} games={GAMES} />)
    fireEvent.change(motto(), { target: { value: "   " } })
    await send()
    expect(update).toHaveBeenCalledWith({ motto: null, games: ["lol"] })
    expect(screen.getByRole("status").textContent).toMatch(/Profil enregistré/)
  })

  it.each([
    [422, "Jeu inconnu ou désactivé : lol", /Jeu inconnu ou désactivé : lol/],
    [403, "Réservé à l'état-major", /ne fais pas partie de l’état-major/],
    [503, "Liste du staff indisponible", /indisponible pour l’instant/],
  ])("erreur %i de l'API affichée lisiblement", async (status, detail, expected) => {
    update.mockRejectedValue(new client.ApiError(status, detail))
    render(<StaffProfileForm motto="Salut" selected={[]} games={GAMES} />)
    await send()
    expect(screen.getByRole("alert").textContent).toMatch(expected)
  })

  it("liste des jeux indisponible : la phrase reste modifiable, les jeux sont conservés", async () => {
    render(<StaffProfileForm motto="Salut" selected={["lol"]} games={null} />)
    expect(screen.queryAllByRole("checkbox")).toHaveLength(0)
    expect(screen.getByText(/Liste des jeux indisponible/)).toBeTruthy()
    await send()
    expect(update).toHaveBeenCalledWith({ motto: "Salut", games: ["lol"] })
  })
})
