import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"
import { AchievementsPanel } from "@/components/members/achievements-panel"
import { ActivityHeatmap, buildWeeks } from "@/components/members/activity-heatmap"
import type { AchievementWithStatus } from "@/lib/api/types"

afterEach(cleanup)

describe("ActivityHeatmap", () => {
  const now = new Date("2026-11-21T12:00:00Z")

  it("52 semaines dimanche → samedi, dernière semaine contenant aujourd'hui", () => {
    const weeks = buildWeeks(now)
    expect(weeks.every(w => w.length === 7)).toBe(true)
    expect(new Date(weeks[0][0]).getUTCDay()).toBe(0)
    const last = weeks[weeks.length - 1]
    expect(last).toContain(Date.UTC(2026, 10, 21))
  })

  it("colore selon le compte, les jours futurs n'ont ni date ni compte", () => {
    const { container } = render(<ActivityHeatmap now={now} data={[{ date: "2026-11-20", count: 20 }, { date: "2026-11-19", count: 1 }]} />)
    expect(container.querySelector('[data-day="2026-11-20"]')!.className).toContain("bg-green")
    expect(container.querySelector('[data-day="2026-11-20"]')!.getAttribute("data-count")).toBe("20")
    expect(container.querySelector('[data-day="2026-11-19"]')!.className).toContain("bg-green/25")
    expect(container.querySelector('[data-day="2026-11-22"]')).toBeNull()
    expect(container.querySelector('[data-day="2026-11-18"]')!.getAttribute("data-count")).toBe("0")
  })
})

describe("AchievementsPanel", () => {
  const ach = (id: number, type: string, unlocked: boolean): AchievementWithStatus => ({
    id, name: `Succès ${id}`, description: "d", icon: "🏅", points: 25, condition_type: type, unlocked, unlocked_at: unlocked ? "2026-11-01T10:00:00Z" : null,
  })
  const many = [ach(1, "messages", true), ach(2, "voice_hours", false), ...Array.from({ length: 12 }, (_, i) => ach(10 + i, "level", false))]

  it("compte les débloqués, grise les manquants", () => {
    render(<AchievementsPanel achievements={many} />)
    expect(screen.getByText("1 sur 14 débloqués")).toBeTruthy()
    expect(screen.getByText("Succès 1").closest("li")!.getAttribute("data-unlocked")).toBe("true")
    expect(screen.getByText("Succès 2").closest("li")!.getAttribute("data-unlocked")).toBe("false")
  })

  it("filtre par catégorie et repagine à 12", () => {
    render(<AchievementsPanel achievements={many} />)
    expect(screen.getAllByRole("listitem")).toHaveLength(12)
    expect(screen.getByText("1 / 2")).toBeTruthy()
    fireEvent.click(screen.getByRole("button", { name: "Vocal" }))
    expect(screen.getAllByRole("listitem")).toHaveLength(1)
    expect(screen.queryByText(/ \/ /)).toBeNull()
    fireEvent.click(screen.getByRole("button", { name: "Tous" }))
    fireEvent.click(screen.getByRole("button", { name: "Page suivante" }))
    expect(screen.getAllByRole("listitem")).toHaveLength(2)
  })
})
