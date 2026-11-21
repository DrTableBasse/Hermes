import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

const api = vi.hoisted(() => ({ getPage: vi.fn() }))
vi.mock("@/lib/api/server", () => api)

import NotFound from "@/app/[locale]/not-found"
import { LegalPage, legalMetadata } from "@/components/legal/legal-page"

afterEach(() => {
  cleanup()
  vi.resetAllMocks()
})

const page = (body_md: string) => ({ slug: "reglement", title: "Règlement", body_md, updated_at: null })

describe("page légale", () => {
  it("affiche « Bientôt » et noindex tant que le texte est vide", async () => {
    api.getPage.mockResolvedValue(page("  \n"))
    render(await LegalPage({ slug: "reglement" }))
    expect(screen.getByRole("heading", { level: 1, name: "Règlement" })).toBeTruthy()
    expect(screen.getByRole("status").textContent).toMatch(/^Bientôt/)
    const meta = await legalMetadata("reglement")
    expect(meta.robots).toEqual({ index: false, follow: false })
    expect(meta.title).toBe("Règlement · SaucisseLand")
  })

  it("traite une API muette comme une page vide", async () => {
    api.getPage.mockResolvedValue(null)
    render(await LegalPage({ slug: "mentions-legales" }))
    expect(screen.getByRole("heading", { level: 1, name: "Mentions légales" })).toBeTruthy()
    expect(screen.getByRole("status")).toBeTruthy()
    expect((await legalMetadata("mentions-legales")).robots).toEqual({ index: false, follow: false })
  })

  it("rend le Markdown sans HTML brut et reste indexable", async () => {
    api.getPage.mockResolvedValue(page("## Article 1\n\nPas de spam.\n\n<script>alert(1)</script>"))
    const { container } = render(await LegalPage({ slug: "reglement" }))
    expect(screen.getByRole("heading", { level: 2, name: "Article 1" })).toBeTruthy()
    expect(container.querySelector("script")).toBeNull()
    expect(screen.queryByRole("status")).toBeNull()
    const meta = await legalMetadata("reglement")
    expect(meta.robots).toBeUndefined()
    expect(meta.openGraph).toMatchObject({ title: "Règlement", locale: "fr_FR" })
    expect(meta.openGraph).not.toHaveProperty("images")
  })
})

describe("404", () => {
  it("propose le retour à l'accueil", () => {
    render(<NotFound />)
    expect(screen.getByRole("heading", { level: 1 })).toBeTruthy()
    expect(screen.getByRole("link", { name: /Retour à l’accueil/ }).getAttribute("href")).toBe("/")
  })
})
