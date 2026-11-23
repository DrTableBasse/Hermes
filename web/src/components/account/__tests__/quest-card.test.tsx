import { act, cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"
import type { Quest } from "@/lib/api/types"

const client = vi.hoisted(() => ({ api: { quests: { claim: vi.fn() } } }))
vi.mock("@/lib/api/client", () => client)

import { QuestCard } from "@/components/account/quest-card"
import { StreakBadge } from "@/components/account/streak-badge"

const quest = (over: Partial<Quest> = {}): Quest => ({
  id: 4,
  title: "Bavard",
  description: null,
  quest_type: "messages",
  target_value: 50,
  xp_reward: 1500,
  icon: null,
  current_progress: 50,
  status: "completed",
  week_start: "2026-11-16",
  week_end: "2026-11-22",
  is_active: true,
  ...over,
})

const claim = client.api.quests.claim

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

const renderCard = (q: Quest) =>
  render(
    <ul>
      <QuestCard quest={q} />
    </ul>,
  )

describe("QuestCard", () => {
  it("quête terminée : réclamer appelle l'API avec l'identifiant puis affiche « Récompense réclamée »", async () => {
    claim.mockResolvedValue({ success: true, xp_reward: 1500 })
    renderCard(quest())
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Réclamer la récompense" }))
    })
    expect(claim).toHaveBeenCalledWith(4)
    expect(screen.getByText("Récompense réclamée")).toBeTruthy()
    expect(screen.queryByRole("button")).toBeNull()
  })

  it("échec de la réclamation : alerte, bouton conservé pour réessayer", async () => {
    claim.mockRejectedValue(new Error("500"))
    renderCard(quest())
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Réclamer la récompense" }))
    })
    expect(screen.getByRole("alert").textContent).toMatch(/pas pu valider/)
    expect(screen.getByRole("button", { name: "Réclamer la récompense" })).toBeTruthy()
  })

  it("quête en cours : progression, pas de bouton", () => {
    renderCard(quest({ status: "active", current_progress: 20 }))
    expect(screen.getByText("20 sur 50")).toBeTruthy()
    expect(screen.getByText("40 %")).toBeTruthy()
    expect(screen.queryByRole("button")).toBeNull()
  })

  it("quête déjà réclamée : pas de bouton", () => {
    renderCard(quest({ status: "claimed" }))
    expect(screen.getByText("Récompense réclamée")).toBeTruthy()
    expect(screen.queryByRole("button")).toBeNull()
  })

  it("cible nulle : pas de division par zéro", () => {
    renderCard(quest({ status: "active", target_value: 0, current_progress: 0 }))
    expect(screen.getByText("0 %")).toBeTruthy()
  })
})

describe("StreakBadge", () => {
  it("rien à 0 jour", () => {
    const { container } = render(<StreakBadge streak={0} />)
    expect(container.firstChild).toBeNull()
  })

  it("annonce la série en jours, au pluriel", () => {
    render(<StreakBadge streak={9} />)
    expect(screen.getByLabelText("Série de 9 jours")).toBeTruthy()
    cleanup()
    render(<StreakBadge streak={1} />)
    expect(screen.getByLabelText("Série de 1 jour")).toBeTruthy()
  })
})
