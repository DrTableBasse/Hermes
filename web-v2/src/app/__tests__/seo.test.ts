import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const api = vi.hoisted(() => ({ listArticles: vi.fn() }))
vi.mock("@/lib/api/server", () => api)
vi.mock("next/server", async importOriginal => ({ ...(await importOriginal<object>()), connection: async () => {} }))
vi.mock("next-intl/middleware", async () => {
  const { NextResponse } = await import("next/server")
  return { default: () => () => NextResponse.next() }
})
vi.mock("@/app/fonts", () => ({ fontVariables: "" }))
vi.mock("@/app/globals.css", () => ({}))
vi.mock("@/components/layout/navbar", () => ({ Navbar: () => null }))
vi.mock("@/components/layout/footer", () => ({ Footer: () => null }))

import { generateMetadata } from "@/app/[locale]/layout"
import robots from "@/app/robots"
import sitemap from "@/app/sitemap"
import { proxy } from "@/proxy"
import { NextRequest } from "next/server"

const PROD = "https://saucisseland.fr"
const indexable = () => vi.stubEnv("SITE_INDEXABLE", "true")

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_APP_URL", PROD)
  vi.stubEnv("BETTER_AUTH_URL", PROD)
  vi.stubEnv("SITE_INDEXABLE", "")
})
afterEach(() => {
  vi.unstubAllEnvs()
  vi.resetAllMocks()
})

describe("robots", () => {
  it("interdit tout par défaut, même sur l'URL de production", () => {
    expect(robots()).toEqual({ rules: { userAgent: "*", disallow: "/" } })
  })
  it("indexable : ferme les zones privées et annonce le sitemap", () => {
    indexable()
    const r = robots()
    expect(r.rules).toEqual({ userAgent: "*", allow: "/", disallow: ["/admin", "/profil", "/editeur", "/quetes", "/tickets"] })
    expect(r.sitemap).toBe(`${PROD}/sitemap.xml`)
  })
})

describe("métadonnées du layout", () => {
  it("noindex partout par défaut, metadataBase lu à l'exécution", async () => {
    const m = await generateMetadata()
    expect(m.robots).toEqual({ index: false, follow: false })
    expect(m.metadataBase?.href).toBe(`${PROD}/`)
  })
  it("indexable : pas de robots restrictif", async () => {
    indexable()
    expect((await generateMetadata()).robots).toBeUndefined()
  })
})

describe("en-tête X-Robots-Tag", () => {
  const request = () => new NextRequest(`${PROD}/profil`)
  it("noindex, nofollow par défaut (y compris sur la redirection d'une zone protégée)", () => {
    expect(proxy(request()).headers.get("X-Robots-Tag")).toBe("noindex, nofollow")
  })
  it("absent quand le site est indexable", () => {
    indexable()
    expect(proxy(request()).headers.get("X-Robots-Tag")).toBeNull()
  })
})

describe("sitemap", () => {
  const article = (slug: string, published = true) => ({ slug, published, updated_at: "2026-11-01T10:00:00Z" })

  it("est vide tant que le site n'est pas indexable", async () => {
    expect(await sitemap()).toEqual([])
    expect(api.listArticles).not.toHaveBeenCalled()
  })

  it("liste les pages publiques en URL absolues et les articles publiés", async () => {
    indexable()
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
    indexable()
    api.listArticles.mockRejectedValue(new Error("500"))
    const urls = (await sitemap()).map(e => e.url)
    expect(urls).toContain(`${PROD}/reglement`)
    expect(urls).toHaveLength(10)
  })

  it("parcourt les pages d'articles", async () => {
    indexable()
    api.listArticles
      .mockResolvedValueOnce({ articles: [article("a")], total: 2, page: 1, limit: 1 })
      .mockResolvedValueOnce({ articles: [article("b")], total: 2, page: 2, limit: 1 })
    const urls = (await sitemap()).map(e => e.url)
    expect(urls).toContain(`${PROD}/articles/a`)
    expect(urls).toContain(`${PROD}/articles/b`)
    expect(api.listArticles).toHaveBeenCalledTimes(2)
  })
})
