import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { afterEach, describe, expect, it, vi } from "vitest"
import { isSameOriginRequest, publicHosts } from "@/lib/api/same-origin"

const hdrs = (o: Record<string, string>) => new Headers(o)
const APP = { NEXT_PUBLIC_APP_URL: "https://saucisseland.fr" }

describe("isSameOriginRequest (constat M4)", () => {
  it("laisse passer les méthodes sûres quelle que soit l'origine", () => {
    expect(isSameOriginRequest("GET", hdrs({ origin: "https://evil.example" }), APP)).toBe(true)
    expect(isSameOriginRequest("HEAD", hdrs({ origin: "null" }), APP)).toBe(true)
  })

  it("refuse une mutation venue d'une autre origine", () => {
    for (const origin of ["https://evil.example", "https://sub.saucisseland.fr", "null", "pas une url"]) {
      expect(isSameOriginRequest("POST", hdrs({ origin, host: "saucisseland.fr" }), APP)).toBe(false)
    }
  })

  it("accepte l'origine du site : hôte de la requête ou URL publique configurée", () => {
    expect(isSameOriginRequest("POST", hdrs({ origin: "http://192.168.10.62:3000", host: "192.168.10.62:3000" }), APP)).toBe(true)
    expect(isSameOriginRequest("DELETE", hdrs({ origin: "https://saucisseland.fr", host: "web:3000" }), APP)).toBe(true)
    expect(isSameOriginRequest("PATCH", hdrs({ origin: "https://saucisseland.fr" }), {})).toBe(false)
  })

  it("sans Origin : seulement Sec-Fetch-Site same-origin ou absent (client non navigateur)", () => {
    expect(isSameOriginRequest("PUT", hdrs({}), APP)).toBe(true)
    expect(isSameOriginRequest("PUT", hdrs({ "sec-fetch-site": "same-origin" }), APP)).toBe(true)
    expect(isSameOriginRequest("PUT", hdrs({ "sec-fetch-site": "same-site" }), APP)).toBe(false)
    expect(isSameOriginRequest("PUT", hdrs({ "sec-fetch-site": "cross-site" }), APP)).toBe(false)
    expect(isSameOriginRequest("PUT", hdrs({ "sec-fetch-site": "none" }), APP)).toBe(false)
  })
})

describe("URL publique lue au runtime (constat m1)", () => {
  afterEach(() => vi.unstubAllEnvs())

  it("proxy qui réécrit Host (Cloudflare Tunnel) : l'URL publique de l'environnement suffit", () => {
    vi.stubEnv("NEXT_PUBLIC_APP_URL", "")
    vi.stubEnv("BETTER_AUTH_URL", "https://saucisseland.fr/")
    const req = hdrs({ origin: "https://saucisseland.fr", host: "localhost:3000" })
    expect(isSameOriginRequest("POST", req)).toBe(true)
    expect(isSameOriginRequest("POST", hdrs({ origin: "https://evil.example", host: "localhost:3000" }))).toBe(false)
  })

  it("la valeur est relue à chaque appel, pas figée au chargement du module", () => {
    vi.stubEnv("BETTER_AUTH_URL", "")
    vi.stubEnv("NEXT_PUBLIC_APP_URL", "https://a.example")
    expect(publicHosts()).toEqual(["a.example"])
    vi.stubEnv("NEXT_PUBLIC_APP_URL", "https://b.example")
    expect(publicHosts()).toEqual(["b.example"])
  })

  it("aucun accès littéral process.env.NEXT_PUBLIC_* (Next l'inlinerait au build, sans .env)", () => {
    const src = readFileSync(resolve(process.cwd(), "src/lib/api/same-origin.ts"), "utf8")
    expect(src.replace(/\/\*[\s\S]*?\*\//g, "")).not.toMatch(/process\.env\s*(\.|\[\s*["'`])\s*NEXT_PUBLIC_/)
  })
})
