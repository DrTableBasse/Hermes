import { describe, expect, it } from "vitest"
import { config } from "@/proxy"

// Next ancre le motif sur le chemin complet.
const matches = (path: string) =>
  config.matcher.some(m => new RegExp(`^${m}$`).test(path))

describe("matcher du proxy", () => {
  it.each(["/", "/admin", "/profil", "/editeur/1", "/fr/profil"])(
    "intercepte %s",
    path => expect(matches(path)).toBe(true),
  )

  it.each(["/favicon.ico", "/api/x", "/_next/static/a.js"])(
    "ignore %s",
    path => expect(matches(path)).toBe(false),
  )
})
