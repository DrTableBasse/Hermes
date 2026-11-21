import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const api = vi.hoisted(() => ({ listArticles: vi.fn() }))
vi.mock("@/lib/api/server", () => api)

import robots from "@/app/robots"
import sitemap from "@/app/sitemap"

const PROD = "https://saucisseland.fr"

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_APP_URL", PROD)
  vi.stubEnv("BETTER_AUTH_URL", PROD)
})
afterEach(() => {
  vi.unstubAllEnvs()
  vi.resetAllMocks()
})

describe("robots", () => {
  it("interdit tout en préproduction", () => {
    vi.stubEnv("NEXT_PUBLIC_APP_URL", "http://192.168.10.62:3002")
    expect(robots()).toEqual({ rules: { userAgent: "*", disallow: "/" } })
  })
  it("en production, ferme les zones privées et annonce le sitemap", () => {
    const r = robots()
    expect(r.rules).toEqual({
      userAgent: "*",
      allow: "/",
      disallow: ["/admin", "/profil", "/editeur", "/quetes", "/tickets"],
    })
    expect(r.sitemap).toBe(`${PROD}/sitemap.xml`)
  })
})

describe("sitemap", () => {
  const article = (slug: string, published = true) => ({ slug, published, updated_at: "2026-11-01T10:00:00Z" })

  it("liste les pages publiques en URL absolues et les articles publiés", async () => {
    api.listArticles.mockResolvedValue({
      articles: [article("hello world"), article("brouillon", false)],
      total: 2,
      page: 1,
      limit: 100,
    })
    const urls = (await sitemap()).map(e => e.url)
    expect(urls).toContain(PROD)
    for (const p of ["progression", "hermes", "galerie", "etat-major", "classement", "top-semaine", "articles", "reglement", "mentions-legales"]) {
      expect(urls).toContain(`${PROD}/${p}`)
    }
    expect(urls).toContain(`${PROD}/articles/hello%20world`)
    expect(urls).not.toContain(`${PROD}/articles/brouillon`)
    expect(urls.every(u => u.startsWith(PROD))).toBe(true)
  })

  it("garde les pages fixes quand l'API est muette", async () => {
    api.listArticles.mockRejectedValue(new Error("500"))
    const urls = (await sitemap()).map(e => e.url)
    expect(urls).toContain(`${PROD}/reglement`)
    expect(urls).toHaveLength(10)
  })

  it("parcourt les pages d'articles", async () => {
    api.listArticles
      .mockResolvedValueOnce({ articles: [article("a")], total: 2, page: 1, limit: 1 })
      .mockResolvedValueOnce({ articles: [article("b")], total: 2, page: 2, limit: 1 })
    const urls = (await sitemap()).map(e => e.url)
    expect(urls).toContain(`${PROD}/articles/a`)
    expect(urls).toContain(`${PROD}/articles/b`)
    expect(api.listArticles).toHaveBeenCalledTimes(2)
  })
})
