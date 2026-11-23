import { existsSync } from "node:fs"
import { describe, expect, it } from "vitest"
// Moteur de correspondance de Next lui-même : les sources sont lues comme en production.
import { getPathMatch } from "next/dist/shared/lib/router/utils/path-match"
import { prepareDestination } from "next/dist/shared/lib/router/utils/prepare-destination"
import { legacyRedirects } from "@/lib/legacy-redirects"

const rules = legacyRedirects()

/** Première règle qui s'applique (Next s'arrête à la première), puis destination compilée. */
function resolve(pathname: string): string | null {
  for (const rule of rules) {
    const params = getPathMatch(rule.source, { removeUnnamedParams: true, strict: true })(pathname)
    if (params) {
      return prepareDestination({ appendParamsToQuery: false, destination: rule.destination, params, query: {} })
        .newUrl
    }
  }
  return null
}

const CASES: Array<[string, string]> = [
  ["/leaderboard", "/classement"],
  ["/profile", "/profil"],
  ["/quests", "/quetes"],
  ["/compare", "/comparer"],
  ["/top-weekly", "/top-semaine"],
  ["/editor/new", "/editeur/nouveau"],
  ["/editor/12", "/editeur/12"],
  ["/fr", "/"],
  ["/en", "/"],
  ["/fr/leaderboard", "/classement"],
  ["/en/leaderboard", "/classement"],
  ["/fr/profile", "/profil"],
  ["/en/quests", "/quetes"],
  ["/fr/compare", "/comparer"],
  ["/en/top-weekly", "/top-semaine"],
  ["/fr/editor/new", "/editeur/nouveau"],
  ["/en/editor/7", "/editeur/7"],
  ["/fr/articles/mon-article", "/articles/mon-article"],
  ["/en/u/123", "/u/123"],
  ["/fr/admin/tickets", "/admin/tickets"],
]

describe("redirections des anciennes URL", () => {
  it.each(CASES)("%s → %s, en une seule redirection", (from, to) => {
    expect(resolve(from)).toBe(to)
    expect(resolve(to)).toBeNull()
  })

  it("toutes permanentes", () => {
    expect(rules.every(r => r.permanent)).toBe(true)
  })

  it("ne touche pas aux pages du nouveau site", () => {
    for (const path of ["/", "/classement", "/profil", "/editeur/nouveau", "/articles/x", "/france", "/english"]) {
      expect(resolve(path)).toBeNull()
    }
  })

  it("chaque destination est une page du nouveau site", () => {
    // Chemin de destination → page de src/app/[locale] (vitest est lancé depuis web : npm test).
    const page = (to: string) =>
      to
        .replace(/^\/editeur\/\d+$/, "/editeur/[id]")
        .replace(/^\/u\/\d+$/, "/u/[userId]")
        .replace(/^\/articles\/[^/]+$/, "/articles/[slug]")
        .replace(/^\/$/, "")
    for (const [, to] of CASES) {
      const file = `src/app/[locale]${page(to)}/page.tsx`
      expect(existsSync(file), file).toBe(true)
    }
  })
})
