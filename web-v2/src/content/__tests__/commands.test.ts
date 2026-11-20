// @vitest-environment node
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs"
import { join } from "node:path"
import { describe, expect, it } from "vitest"
import { BOT_COMMANDS, COMMAND_GROUPS } from "@/content/commands"

const COGS = join(__dirname, "..", "..", "..", "..", "bot", "cogs")

function pythonFiles(dir: string): string[] {
  return readdirSync(dir).flatMap(name => {
    const path = join(dir, name)
    if (statSync(path).isDirectory()) return name === "__pycache__" ? [] : pythonFiles(path)
    return name.endsWith(".py") ? [path] : []
  })
}

/** Commandes slash déclarées dans les cogs, avec leur réservation au staff (décorateurs de la commande). */
function cogCommands(): Map<string, boolean> {
  const found = new Map<string, boolean>()
  for (const file of pythonFiles(COGS)) {
    const source = readFileSync(file, "utf8")
    const groups = new Map<string, string>()
    for (const m of source.matchAll(/(\w+)\s*=\s*app_commands\.Group\(\s*name="([^"]+)"/g)) groups.set(m[1], m[2])
    for (const m of source.matchAll(/@(\w+(?:\.\w+)?)\.command\(\s*name="([^"]+)"/g)) {
      const owner = m[1]
      const prefix = owner === "app_commands" ? "" : `${groups.get(owner) ?? owner} `
      // Décorateurs empilés jusqu'à la fonction : c'est là que se trouve la réservation.
      const start = m.index ?? 0
      const decorators = source.slice(start, source.indexOf("async def", start))
      found.set(`${prefix}${m[2]}`, /administration_only\(\)|has_permissions\(/.test(decorators))
    }
  }
  return found
}

describe("commandes affichées sur /hermes", () => {
  it("chaque commande a un nom unique, un groupe connu et un commentaire", () => {
    const names = BOT_COMMANDS.map(c => c.name)
    expect(new Set(names).size).toBe(names.length)
    const groups = new Set(COMMAND_GROUPS.map(g => g.id))
    for (const c of BOT_COMMANDS) {
      expect(groups.has(c.group)).toBe(true)
      expect(c.comment.length).toBeGreaterThan(10)
      expect(c.name.startsWith("/")).toBe(false)
      // Le groupe « staff » et le drapeau vont ensemble.
      expect(c.group === "staff").toBe(c.staff === true)
    }
  })

  // Hors dépôt complet (image Docker de web-v2), les cogs ne sont pas là : rien à comparer.
  it.skipIf(!existsSync(COGS))("suit exactement les cogs du bot, réservations au staff comprises", () => {
    const cogs = cogCommands()
    expect(cogs.size).toBeGreaterThan(30)
    expect(new Set(BOT_COMMANDS.map(c => c.name))).toEqual(new Set(cogs.keys()))
    for (const c of BOT_COMMANDS) expect([c.name, c.staff === true]).toEqual([c.name, cogs.get(c.name)])
  })
})
