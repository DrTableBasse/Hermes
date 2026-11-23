import { readFileSync } from "node:fs"
import { join } from "node:path"
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

  it("copie fournie : rendue à la place des éléments, cachée mais cliquable", () => {
    const { container } = render(
      <Marquee items={[<button key="a">Original</button>]} copy={[<button key="a" tabIndex={-1}>Copie</button>]} />,
    )
    const groups = container.querySelectorAll("[data-marquee-group]")
    expect(groups[0].textContent).toBe("Original")
    expect(groups[1].textContent).toBe("Copie")
    expect(groups[1].getAttribute("aria-hidden")).toBe("true")
    expect(groups[1].hasAttribute("inert")).toBe(false)
  })

  it("rend la région nommée focusable, pour la mettre en pause au clavier", () => {
    const { getByRole } = render(<Marquee items={["x"]} aria-label="Tous nos jeux" />)
    expect(getByRole("region", { name: "Tous nos jeux" }).getAttribute("tabindex")).toBe("0")
    // Sans nom, pas de région : rien à annoncer, donc pas d'arrêt de tabulation vide.
    const { container: anonymous } = render(<Marquee items={["y"]} />)
    expect(anonymous.querySelector(".marquee")?.hasAttribute("tabindex")).toBe(false)
  })

  it("anime la piste par un utilitaire du thème, sans quoi Tailwind n'émet pas le keyframe", () => {
    const { container } = render(<Marquee items={["x"]} />)
    const track = container.querySelector("[data-marquee-track]") as HTMLElement
    expect(track.classList.contains("animate-marquee")).toBe(true)
    // Le keyframe n'existe dans le CSS final que s'il est référencé par --animate-marquee.
    const css = readFileSync(join(__dirname, "../../../app/globals.css"), "utf8")
    expect(css).toMatch(/--animate-marquee:\s*defile\b/)
    expect(css).toMatch(/@keyframes defile/)
  })

  it("inverse le sens et règle la vitesse à la demande", () => {
    const { container } = render(<Marquee items={["x"]} reverse speed={55} />)
    const track = container.querySelector("[data-marquee-track]") as HTMLElement
    expect(track.style.animationDirection).toBe("reverse")
    expect(track.style.animationDuration).toBe("55s")
  })
})
