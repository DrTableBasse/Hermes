// @vitest-environment node
import { readFileSync } from "node:fs"
import { join } from "node:path"
import { compile } from "@tailwindcss/node"
import postcss, { type AtRule, type Rule } from "postcss"
import { describe, expect, it } from "vitest"

const appDir = join(__dirname, "..")

/** CSS final de globals.css tel que Tailwind le produit pour les classes données. */
async function buildCss(candidates: string[]): Promise<string> {
  const source = readFileSync(join(appDir, "globals.css"), "utf8")
  const compiler = await compile(source, { base: appDir, onDependency: () => {} })
  return compiler.build(candidates)
}

/**
 * Rang de cascade d'une règle : les couches dans l'ordre de déclaration, puis le CSS hors couche,
 * qui l'emporte sur toutes (hors !important). Plus grand = gagne.
 */
function cascadeRank(rule: Rule, layerOrder: string[]): number {
  let node = rule.parent
  while (node && node.type !== "root") {
    if (node.type === "atrule" && (node as AtRule).name === "layer") {
      return layerOrder.indexOf((node as AtRule).params.trim())
    }
    node = node.parent
  }
  return layerOrder.length
}

describe("globals.css, cascade du bandeau", () => {
  it("la pause au survol et au focus l'emporte sur le raccourci animation de animate-marquee", async () => {
    const root = postcss.parse(await buildCss(["animate-marquee", "marquee", "marquee-pause", "marquee-track"]))

    const order = root.nodes
      .filter((n): n is AtRule => n.type === "atrule" && n.name === "layer" && !n.nodes)
      .flatMap(n => n.params.split(",").map(s => s.trim()))
    expect(order).toContain("utilities")

    let animateRank = -1
    const pauseRanks: Record<string, number> = {}
    root.walkRules(rule => {
      const decls = rule.nodes.filter(n => n.type === "decl")
      if (rule.selector === ".animate-marquee" && decls.some(d => d.prop === "animation")) {
        animateRank = cascadeRank(rule, order)
      }
      if (decls.some(d => d.prop === "animation-play-state" && d.value === "paused")) {
        for (const state of [":hover", ":focus-within"]) {
          if (rule.selector.includes(`.marquee-pause${state}`)) pauseRanks[state] = cascadeRank(rule, order)
        }
      }
    })

    expect(animateRank).toBeGreaterThanOrEqual(0)
    for (const state of [":hover", ":focus-within"]) {
      expect(pauseRanks[state], `règle de pause ${state}`).toBeDefined()
      expect(pauseRanks[state], `pause ${state} masquée par animate-marquee`).toBeGreaterThan(animateRank)
    }
  })
})
