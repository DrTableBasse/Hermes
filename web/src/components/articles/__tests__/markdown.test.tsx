import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"
import { Markdown } from "@/components/articles/markdown"

afterEach(cleanup)

describe("Markdown", () => {
  it("rend le Markdown GFM : titres, listes, tableaux", () => {
    const { container } = render(
      <Markdown>{"## Sous-titre\n\n- un\n- deux\n\n| a | b |\n|---|---|\n| 1 | 2 |\n"}</Markdown>,
    )
    expect(screen.getByRole("heading", { level: 2, name: "Sous-titre" })).toBeTruthy()
    expect(screen.getAllByRole("listitem")).toHaveLength(2)
    expect(container.querySelector("table")).not.toBeNull()
  })

  it("n'interprète jamais le HTML brut : il reste du texte", () => {
    const { container } = render(
      <Markdown>{'<script>window.x=1</script>\n\n<img src=x onerror="alert(1)">\n\n<b>gras</b>'}</Markdown>,
    )
    expect(container.querySelector("script")).toBeNull()
    expect(container.querySelector("img")).toBeNull()
    expect(container.querySelector("b")).toBeNull()
    expect(container.textContent).toContain("<script>")
  })

  it("liens externes : nouvel onglet, noopener noreferrer nofollow ; liens internes inchangés", () => {
    render(<Markdown>{"[ext](https://exemple.org/page) et [int](/articles/x)"}</Markdown>)
    const ext = screen.getByRole("link", { name: "ext" })
    expect(ext.getAttribute("rel")).toBe("noopener noreferrer nofollow")
    expect(ext.getAttribute("target")).toBe("_blank")
    const int = screen.getByRole("link", { name: "int" })
    expect(int.getAttribute("rel")).toBeNull()
    expect(int.getAttribute("target")).toBeNull()
  })

  it("neutralise les liens javascript:", () => {
    render(<Markdown>{"[piège](javascript:alert(1))"}</Markdown>)
    const link = screen.queryByRole("link", { name: "piège" })
    expect(link?.getAttribute("href") ?? "").not.toMatch(/^javascript:/i)
  })

  it("images : volume média et CDN Discord affichés, autre hôte réduit à son texte", () => {
    const { container } = render(
      <Markdown>
        {
          "![ok](/media/a.png) ![discord](https://cdn.discordapp.com/x/y.png) ![tracker](https://evil.example/t.png)"
        }
      </Markdown>,
    )
    const srcs = [...container.querySelectorAll("img")].map(i => i.getAttribute("src"))
    expect(srcs).toEqual(["/media/a.png", "https://cdn.discordapp.com/x/y.png"])
    expect(container.textContent).toContain("tracker")
  })

  it("colore les blocs de code d'un langage connu, laisse les autres en texte brut", () => {
    const { container } = render(
      <Markdown>{'```js\nconst a = "x"\n```\n\n```langageinconnu\nrien\n```'}</Markdown>,
    )
    expect(container.querySelector("code.language-js .hljs-keyword")).not.toBeNull()
    expect(container.textContent).toContain("rien")
  })
})
