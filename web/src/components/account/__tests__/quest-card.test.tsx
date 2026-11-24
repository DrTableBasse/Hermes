import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"
import type { Quest } from "@/lib/api/types"

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

afterEach(() => {
  cleanup()
})

const renderCard = (q: Quest) =>
  render(
    <ul>
      <QuestCard quest={q} />
    </ul>,
  )

describe("QuestCard", () => {
  it("quête terminée : récompense versée automatiquement, aucun bouton à cliquer", () => {
    renderCard(quest())
    expect(screen.getByText("Terminé : Hermes ajoute la récompense à ton XP")).toBeTruthy()
    expect(screen.queryByRole("button")).toBeNull()
  })

  it("quête en cours : progression, pas de bouton", () => {
    renderCard(quest({ status: "active", current_progress: 20 }))
    expect(screen.getByText("20 sur 50")).toBeTruthy()
    expect(screen.getByText("40 %")).toBeTruthy()
    expect(screen.queryByRole("button")).toBeNull()
  })

  it("récompense versée : message de confirmation, pas de bouton", () => {
    renderCard(quest({ status: "claimed" }))
    expect(screen.getByText("Récompense ajoutée à ton XP")).toBeTruthy()
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
