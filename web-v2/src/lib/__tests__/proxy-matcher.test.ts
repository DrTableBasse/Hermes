import { describe, expect, it } from "vitest"
import { config } from "@/proxy"

// Next ancre le motif sur le chemin complet.
const matches = (path: string) =>
  config.matcher.some(m => new RegExp(`^${m}$`).test(path))

describe("matcher du proxy", () => {
  it.each(["/", "/admin", "/profil", "/editeur/1", "/fr/profil", "/_kitchen"])(
    "intercepte %s",
    path => expect(matches(path)).toBe(true),
  )

  // /_kit a son propre layout racine, hors [locale] : next-intl ne doit pas le réécrire en /fr/_kit.
  it.each(["/favicon.ico", "/api/x", "/_next/static/a.js", "/_kit", "/_kit/x"])(
    "ignore %s",
    path => expect(matches(path)).toBe(false),
  )
})
