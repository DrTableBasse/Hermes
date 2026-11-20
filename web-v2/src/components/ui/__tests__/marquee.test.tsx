import { render } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { Marquee } from "@/components/ui/marquee"

describe("Marquee", () => {
  it("duplique le contenu une fois et masque la copie aux lecteurs d'écran", () => {
    const { container, getAllByText } = render(
      <Marquee items={[<span key="a">Dead by Daylight</span>, <span key="b">Minecraft</span>]} />,
    )
    expect(getAllByText("Dead by Daylight")).toHaveLength(2)

    const groups = container.querySelectorAll("[data-marquee-group]")
    expect(groups).toHaveLength(2)
    expect(groups[0].getAttribute("aria-hidden")).toBeNull()
    expect(groups[1].getAttribute("aria-hidden")).toBe("true")
    // La copie ne doit pas non plus recevoir le focus clavier.
    expect(groups[1].hasAttribute("inert")).toBe(true)
  })

  it("inverse le sens et règle la vitesse à la demande", () => {
    const { container } = render(<Marquee items={["x"]} reverse speed={55} />)
    const track = container.querySelector("[data-marquee-track]") as HTMLElement
    expect(track.style.animationDirection).toBe("reverse")
    expect(track.style.animationDuration).toBe("55s")
  })
})
