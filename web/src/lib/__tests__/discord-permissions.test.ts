import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { describe, expect, it } from "vitest"
import { PERMISSION_FAMILIES } from "@/lib/discord-permissions"

/** Lit FAMILIES dans bot/utils/permission_catalog.py : [famille, [(clé, libellé)…]]. */
function pythonCatalog(): { family: string; permissions: { key: string; label: string }[] }[] {
  const source = readFileSync(resolve(__dirname, "../../../../bot/utils/permission_catalog.py"), "utf-8")
  const block = source.slice(source.indexOf("FAMILIES"), source.indexOf("_LABELS"))
  const result: { family: string; permissions: { key: string; label: string }[] }[] = []
  for (const line of block.split("\n")) {
    const fam = /^\s*\("([^"]+)", \[\s*$/.exec(line)
    if (fam) {
      result.push({ family: fam[1], permissions: [] })
      continue
    }
    const perm = /^\s*\("([a-z_]+)", "([^"]+)"\),\s*$/.exec(line)
    if (perm && result.length) result[result.length - 1].permissions.push({ key: perm[1], label: perm[2] })
  }
  return result
}

describe("catalogue des permissions Discord", () => {
  it("est identique à celui du bot (clé, famille, libellé)", () => {
    const py = pythonCatalog()
    expect(py.length).toBeGreaterThan(0)
    expect(PERMISSION_FAMILIES).toEqual(py)
  })

  it("ne contient aucune clé en double", () => {
    const keys = PERMISSION_FAMILIES.flatMap(f => f.permissions.map(p => p.key))
    expect(new Set(keys).size).toBe(keys.length)
  })
})
