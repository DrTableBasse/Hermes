import { readdirSync, readFileSync } from "node:fs"
import { join, relative, sep } from "node:path"
import { describe, expect, it } from "vitest"

// vitest est lancé depuis web (npm test).
const SRC = join(process.cwd(), "src")
const IMPORT = /from\s+["']@\/components\/home\/final-cta["']|from\s+["'][./]+final-cta["']/

function sourceFiles(dir: string): string[] {
  return readdirSync(dir, { recursive: true, encoding: "utf8" })
    .filter(f => /\.(ts|tsx)$/.test(f) && !f.split(sep).includes("__tests__"))
    .map(f => join(dir, f))
}

describe("FinalCta", () => {
  it("n'est importé que par l'accueil, src/app/[locale]/page.tsx", () => {
    const importers = sourceFiles(join(SRC, "app"))
      .filter(f => IMPORT.test(readFileSync(f, "utf8")))
      .map(f => relative(SRC, f).split(sep).join("/"))
    expect(importers).toEqual(["app/[locale]/page.tsx"])
  })

  it("aucun composant (layout, navbar, pied de page…) ne l'importe non plus", () => {
    const importers = sourceFiles(join(SRC, "components")).filter(f => IMPORT.test(readFileSync(f, "utf8")))
    expect(importers).toEqual([])
  })
})
