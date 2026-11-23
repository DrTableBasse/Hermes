import { cleanup, render, screen, waitFor } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

const list = vi.hoisted(() => vi.fn())
vi.mock("@/lib/api/client", () => ({ api: { comments: { list, create: vi.fn(), delete: vi.fn(), vote: vi.fn() } } }))

import { ArticleComments } from "@/components/articles/article-comments"

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe("ArticleComments", () => {
  it("chargement : aucun compteur ni « aucun commentaire » avant la réponse", async () => {
    list.mockReturnValue(new Promise(() => {}))
    render(<ArticleComments articleId={1} viewer={null} />)
    expect(screen.getByRole("heading", { name: "Commentaires" })).toBeTruthy()
    expect(screen.queryByText(/Aucun commentaire/)).toBeNull()
  })

  it("échec du chargement : message d'indisponibilité, pas de « (0) » fictif", async () => {
    list.mockRejectedValue(new Error("503"))
    render(<ArticleComments articleId={1} viewer={null} />)
    await waitFor(() => expect(screen.getByRole("status").textContent).toMatch(/indisponibles/))
    expect(screen.getByRole("heading", { name: "Commentaires" })).toBeTruthy()
    expect(screen.queryByText(/\(0\)/)).toBeNull()
    expect(screen.queryByText(/Aucun commentaire/)).toBeNull()
  })

  it("succès : compteur réel ; liste vide : message dédié", async () => {
    list.mockResolvedValue({ comments: [] })
    render(<ArticleComments articleId={1} viewer={null} />)
    await waitFor(() => expect(screen.getByRole("heading", { name: "Commentaires (0)" })).toBeTruthy())
    expect(screen.getByText(/Aucun commentaire/)).toBeTruthy()
  })
})
