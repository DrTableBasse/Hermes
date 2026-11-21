import { cleanup, render, screen, within } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import type { Article } from "@/lib/api/types"

const cookieJar = vi.hoisted(() => new Map<string, string>())
vi.mock("next/headers", () => ({
  cookies: async () => ({ get: (name: string) => (cookieJar.has(name) ? { value: cookieJar.get(name) } : undefined) }),
}))

const nav = vi.hoisted(() => ({
  notFound: vi.fn(() => {
    throw new Error("NEXT_NOT_FOUND")
  }),
  redirect: vi.fn((to: string) => {
    throw new Error(`NEXT_REDIRECT ${to}`)
  }),
}))
vi.mock("next/navigation", () => ({
  ...nav,
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn(), back: vi.fn() }),
  usePathname: () => "/articles",
  useSearchParams: () => new URLSearchParams(),
}))

const api = vi.hoisted(() => ({
  getSessionUser: vi.fn(),
  listArticles: vi.fn(),
  listTags: vi.fn(),
  myArticles: vi.fn(),
  getArticle: vi.fn(),
  getArticleById: vi.fn(),
}))
vi.mock("@/lib/api/server", () => api)

vi.mock("@/lib/api/client", () => ({
  api: { comments: { list: vi.fn().mockResolvedValue({ comments: [] }) }, tags: {}, articles: {}, media: {} },
}))

import ArticlesPage from "@/app/[locale]/articles/page"
import ArticlePage from "@/app/[locale]/articles/[slug]/page"
import EditArticlePage from "@/app/[locale]/editeur/[id]/page"
import NewArticlePage from "@/app/[locale]/editeur/nouveau/page"

const article = (id: number, over: Partial<Article> = {}): Article => ({
  id,
  author_id: "100",
  title: `Article ${id}`,
  slug: `article-${id}`,
  content: "# Bonjour\n\nContenu **riche**.",
  cover_image_url: null,
  published: true,
  created_at: "2026-11-10T10:00:00Z",
  updated_at: "2026-11-10T10:00:00Z",
  tags: [{ id: 1, name: "Annonces", slug: "annonces", color: "#3b82f6" }],
  author: { user_id: "100", username: "Camille", discord_avatar: null },
  ...over,
})

const listOf = (articles: Article[], total = articles.length) => ({ articles, total, page: 1, limit: 12 })
const member = (over = {}) => ({ user_id: "100", is_admin: false, is_redacteur: false, ...over })

beforeEach(() => {
  api.getSessionUser.mockResolvedValue(null)
  api.listArticles.mockResolvedValue(listOf([article(1), article(2)], 30))
  api.listTags.mockResolvedValue([{ id: 1, name: "Annonces", slug: "annonces", color: "#3b82f6" }])
  api.myArticles.mockResolvedValue([])
  api.getArticle.mockResolvedValue(article(1))
  api.getArticleById.mockResolvedValue(article(1))
})

afterEach(() => {
  cleanup()
  cookieJar.clear()
  vi.clearAllMocks()
})

const list = (params: Record<string, string | string[]> = {}) => ArticlesPage({ searchParams: Promise.resolve(params) })

describe("page /articles", () => {
  it("visiteur : grille, filtre de tags, pagination ; ni brouillons ni outils de rédaction", async () => {
    render(await list())
    expect(screen.getByRole("heading", { level: 1, name: "Articles" })).toBeTruthy()
    expect(screen.getByRole("link", { name: "Article 1" }).getAttribute("href")).toBe("/articles/article-1")
    expect(screen.getByRole("navigation", { name: "Filtrer par tag" })).toBeTruthy()
    expect(screen.getByRole("navigation", { name: "Pagination des articles" })).toBeTruthy()
    expect(screen.queryByText("Nouvel article")).toBeNull()
    expect(screen.queryByText("Gérer les tags")).toBeNull()
    expect(api.listArticles).toHaveBeenCalledWith({ page: 1, limit: 12, tag: undefined, search: undefined })
    expect(api.myArticles).not.toHaveBeenCalled()
  })

  it("paramètres d'URL transmis à web-api (tag, recherche, page) ; page invalide ramenée à 1", async () => {
    render(await list({ tag: "annonces", q: " hermes ", page: "abc" }))
    expect(api.listArticles).toHaveBeenCalledWith({ page: 1, limit: 12, tag: "annonces", search: "hermes" })
    expect(screen.getByText(/pour/).textContent).toContain("hermes")
    expect(screen.getByRole("link", { name: "Annonces" }).getAttribute("aria-current")).toBe("page")
  })

  it("rédacteur : session lue avec son jeton, brouillons, nouvel article et gestion des tags", async () => {
    cookieJar.set("better-auth.session_token", "tok")
    api.getSessionUser.mockResolvedValue(member({ is_redacteur: true }))
    api.myArticles.mockResolvedValue([article(5, { published: false, title: "Mon brouillon" }), article(6)])
    render(await list())
    expect(api.myArticles).toHaveBeenCalledWith("tok")
    const drafts = screen.getByRole("region", { name: /Mes brouillons/ })
    expect(within(drafts).getByText("Mon brouillon")).toBeTruthy()
    expect(within(drafts).queryByText("Article 6")).toBeNull()
    expect(within(drafts).getByRole("link", { name: "Modifier" }).getAttribute("href")).toBe("/editeur/5")
    expect(screen.getByRole("link", { name: "Nouvel article" }).getAttribute("href")).toBe("/editeur/nouveau")
    expect(screen.getByText("Gérer les tags")).toBeTruthy()
  })

  it("API indisponible : état dégradé, pas d'erreur ; aucun article : message dédié", async () => {
    api.listArticles.mockRejectedValue(new Error("503 /articles"))
    api.listTags.mockRejectedValue(new Error("503 /tags"))
    render(await list())
    expect(screen.getByRole("status").textContent).toMatch(/injoignables/)
    cleanup()

    api.listArticles.mockResolvedValue(listOf([]))
    render(await list({ q: "zzz" }))
    expect(screen.getByRole("status").textContent).toContain("Aucun résultat pour « zzz »")
  })
})

const show = (slug = "article-1") => ArticlePage({ params: Promise.resolve({ slug }) })

describe("page /articles/[slug]", () => {
  it("article publié : titre, auteur, date, contenu rendu, commentaires ; pas d'actions pour un visiteur", async () => {
    render(await show())
    expect(screen.getByRole("heading", { level: 1, name: "Article 1" })).toBeTruthy()
    expect(screen.getByText("Camille")).toBeTruthy()
    expect(screen.getByText(/10 novembre 2026/)).toBeTruthy()
    expect(screen.getByRole("heading", { level: 1, name: "Bonjour" })).toBeTruthy()
    expect(screen.getByRole("heading", { name: /Commentaires/ })).toBeTruthy()
    expect(screen.queryByRole("link", { name: "Modifier" })).toBeNull()
    expect(api.getArticle).toHaveBeenCalledWith("article-1", undefined)
  })

  it("auteur : actions de modification ; autre rédacteur : aucune", async () => {
    cookieJar.set("better-auth.session_token", "tok")
    api.getSessionUser.mockResolvedValue(member())
    render(await show())
    expect(screen.getByRole("link", { name: "Modifier" }).getAttribute("href")).toBe("/editeur/1")
    expect(api.getArticle).toHaveBeenCalledWith("article-1", "tok")
    cleanup()

    api.getSessionUser.mockResolvedValue(member({ user_id: "999", is_redacteur: true }))
    render(await show())
    expect(screen.queryByRole("link", { name: "Modifier" })).toBeNull()
  })

  it("brouillon : mention explicite, sans commentaires", async () => {
    api.getArticle.mockResolvedValue(article(3, { published: false }))
    render(await show())
    expect(screen.getByText("Brouillon — non publié")).toBeTruthy()
    expect(screen.queryByRole("heading", { name: /Commentaires/ })).toBeNull()
  })

  it("auteur inconnu (a quitté la base) : tiret, page affichée", async () => {
    api.getArticle.mockResolvedValue(article(4, { author: null }))
    render(await show())
    expect(screen.getByText(/Par/).textContent).toContain("—")
  })

  it("article inconnu ou brouillon d'un autre (404) : notFound ; API muette : message dégradé", async () => {
    api.getArticle.mockRejectedValue(new Error("404 /articles/x"))
    await expect(show("x")).rejects.toThrow("NEXT_NOT_FOUND")

    api.getArticle.mockRejectedValue(new Error("502 /articles/x"))
    render(await show("x"))
    expect(screen.getByRole("status").textContent).toMatch(/injoignable/)
  })
})

describe("pages /editeur", () => {
  it("nouvel article : réservé aux rédacteurs et administrateurs, redirection sinon", async () => {
    await expect(NewArticlePage()).rejects.toThrow("NEXT_REDIRECT /")

    cookieJar.set("better-auth.session_token", "tok")
    api.getSessionUser.mockResolvedValue(member())
    await expect(NewArticlePage()).rejects.toThrow("NEXT_REDIRECT /")

    api.getSessionUser.mockResolvedValue(member({ is_redacteur: true }))
    render(await NewArticlePage())
    expect(screen.getByRole("heading", { level: 1, name: "Nouvel article" })).toBeTruthy()
    expect(screen.getByRole("button", { name: "Publier" })).toBeTruthy()
  })

  it("modification : auteur ou admin ; id numérique via /articles/by-id, slug via /articles/{slug}", async () => {
    const edit = (id: string) => EditArticlePage({ params: Promise.resolve({ id }) })
    cookieJar.set("better-auth.session_token", "tok")
    api.getSessionUser.mockResolvedValue(member())

    render(await edit("1"))
    expect(api.getArticleById).toHaveBeenCalledWith(1, "tok")
    expect((screen.getByLabelText("Titre de l'article") as HTMLInputElement).value).toBe("Article 1")
    expect(screen.getByRole("button", { name: "Mettre à jour et publier" })).toBeTruthy()
    cleanup()

    await edit("mon-slug").then(
      node => render(node),
      () => {},
    )
    expect(api.getArticle).toHaveBeenCalledWith("mon-slug", "tok")
    cleanup()

    // Un rédacteur qui n'est pas l'auteur ne peut pas modifier : web-api répondrait 403.
    api.getSessionUser.mockResolvedValue(member({ user_id: "999", is_redacteur: true }))
    await expect(edit("1")).rejects.toThrow("NEXT_REDIRECT /")
    api.getSessionUser.mockResolvedValue(member({ user_id: "999", is_admin: true }))
    render(await edit("1"))
    expect(screen.getByLabelText("Titre de l'article")).toBeTruthy()
  })

  it("modification : article inconnu → notFound ; API muette → message ; sans session → redirection", async () => {
    const edit = (id: string) => EditArticlePage({ params: Promise.resolve({ id }) })
    await expect(edit("1")).rejects.toThrow("NEXT_REDIRECT /")

    cookieJar.set("better-auth.session_token", "tok")
    api.getSessionUser.mockResolvedValue(member())
    api.getArticleById.mockRejectedValue(new Error("404 /articles/by-id/9"))
    await expect(edit("9")).rejects.toThrow("NEXT_NOT_FOUND")

    api.getArticleById.mockRejectedValue(new Error("500 /articles/by-id/9"))
    render(await edit("9"))
    expect(screen.getByRole("status").textContent).toMatch(/injoignable/)
  })
})
