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

/** Lit une instruction Python (décorateur) à partir de `from`, jusqu'à l'équilibre des parenthèses ; chaînes ignorées. */
function readStatement(lines: string[], from: number): { text: string; next: number } {
  let depth = 0
  let quote: string | null = null
  const parts: string[] = []
  let i = from
  for (; i < lines.length; i++) {
    const line = lines[i]
    parts.push(line)
    for (let k = 0; k < line.length; k++) {
      const ch = line[k]
      if (quote) {
        if (ch === "\\") k++
        else if (ch === quote) quote = null
      } else if (ch === '"' || ch === "'") quote = ch
      else if (ch === "#") break
      else if (ch === "(" || ch === "[" || ch === "{") depth++
      else if (ch === ")" || ch === "]" || ch === "}") depth--
    }
    if (depth <= 0 && !quote) break
  }
  return { text: parts.join("\n"), next: i + 1 }
}

/** Valeur d'un argument nommé en chaîne, guillemets simples ou doubles. */
function stringArg(text: string, key: string): string | undefined {
  return new RegExp(String.raw`[(,]\s*${key}\s*=\s*(["'])((?:(?!\1).)*)\1`, "s").exec(text)?.[2]
}

const COMMAND_DECORATOR = /^\s*@([\w.]+)\.command\(/
const isRawCommand = (line: string) => /\.command\(/.test(line) && !/^\s*#/.test(line)

/**
 * Commandes slash déclarées dans les cogs, avec leur réservation au staff.
 * Les décorateurs contigus (au-dessus comme au-dessous de `.command(`) sont lus jusqu'au `def` suivant,
 * qui borne le segment. `rawCount` = nombre de `.command(` bruts : s'il dépasse les commandes reconnues,
 * le test échoue au lieu de laisser un trou silencieux.
 */
function cogCommands(): { found: Map<string, boolean>; rawCount: number } {
  const found = new Map<string, boolean>()
  let rawCount = 0
  for (const file of pythonFiles(COGS)) {
    const lines = readFileSync(file, "utf8").split(/\r?\n/)
    rawCount += lines.filter(isRawCommand).length
    const groups = new Map<string, string>()
    let block: string[] = []
    for (let i = 0; i < lines.length; ) {
      const line = lines[i]
      const trimmed = line.trim()
      const group = /^\s*(\w+)\s*=\s*app_commands\.Group\(/.exec(line)
      if (group) {
        const { text, next } = readStatement(lines, i)
        groups.set(group[1], stringArg(text, "name") ?? group[1])
        i = next
        continue
      }
      if (trimmed.startsWith("@")) {
        const { text, next } = readStatement(lines, i)
        block.push(text)
        i = next
        continue
      }
      const def = /^\s*(?:async\s+)?def\s+(\w+)/.exec(line)
      if (def) {
        const own = block.filter(d => COMMAND_DECORATOR.test(d))
        if (own.length > 1) throw new Error(`${file} : plusieurs .command( sur ${def[1]}`)
        if (own.length === 1) {
          const owner = COMMAND_DECORATOR.exec(own[0])![1]
          // `bot.tree` & co ne sont pas des groupes : seuls `app_commands` et un Group déclaré sont admis.
          if (owner !== "app_commands" && !groups.has(owner)) {
            throw new Error(`${file} : propriétaire de commande inconnu « ${owner} » (${def[1]})`)
          }
          const name = stringArg(own[0], "name") ?? def[1]
          const prefix = owner === "app_commands" ? "" : `${groups.get(owner)} `
          const others = block.filter(d => d !== own[0]).join("\n")
          found.set(`${prefix}${name}`, /administration_only\(\)|has_permissions\(/.test(others))
        }
        block = []
      } else if (trimmed !== "" && !trimmed.startsWith("#")) block = []
      i++
    }
  }
  return { found, rawCount }
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

  // Hors dépôt complet (image Docker du site), les cogs ne sont pas là : rien à comparer.
  it.skipIf(!existsSync(COGS))("suit exactement les cogs du bot, réservations au staff comprises", () => {
    const { found: cogs, rawCount } = cogCommands()
    // Un .command( non reconnu (guillemets, ordre des décorateurs, propriétaire inattendu) ne doit pas passer inaperçu.
    expect(cogs.size).toBe(rawCount)
    expect(new Set(BOT_COMMANDS.map(c => c.name))).toEqual(new Set(cogs.keys()))
    for (const c of BOT_COMMANDS) expect([c.name, c.staff === true]).toEqual([c.name, cogs.get(c.name)])
  })
})
