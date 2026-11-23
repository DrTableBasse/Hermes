import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

vi.mock("next/navigation", () => ({ usePathname: () => "/" }))
vi.mock("@/lib/auth-client", () => ({
  authClient: {
    useSession: { listen: () => () => {}, get: () => null },
    signIn: { social: vi.fn() },
    signOut: vi.fn(),
  },
}))

import { Navbar } from "@/components/layout/navbar"

describe("Navbar, menu mobile", () => {
  it("rend le focus au bouton du menu quand Échap ferme le panneau", () => {
    render(<Navbar inviteUrl={null} />)
    const trigger = screen.getByRole("button", { name: "Ouvrir le menu" })
    fireEvent.click(trigger)

    const link = screen.getAllByRole("link", { name: "Progression" }).at(-1)!
    link.focus()
    expect(document.activeElement).toBe(link)

    fireEvent.keyDown(document, { key: "Escape" })

    expect(trigger.getAttribute("aria-expanded")).toBe("false")
    expect(document.activeElement).toBe(trigger)
  })
})
