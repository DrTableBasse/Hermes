import { describe, expect, it } from "vitest"
import { isSameOriginRequest } from "@/lib/api/same-origin"

const hdrs = (o: Record<string, string>) => new Headers(o)
const APP = "https://saucisseland.fr"

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

  it("accepte l'origine du site : hôte de la requête ou NEXT_PUBLIC_APP_URL", () => {
    expect(isSameOriginRequest("POST", hdrs({ origin: "http://192.168.10.62:3000", host: "192.168.10.62:3000" }), APP)).toBe(true)
    expect(isSameOriginRequest("DELETE", hdrs({ origin: "https://saucisseland.fr", host: "web:3000" }), APP)).toBe(true)
    expect(isSameOriginRequest("PATCH", hdrs({ origin: "https://saucisseland.fr" }), undefined)).toBe(false)
  })

  it("sans Origin : seulement Sec-Fetch-Site same-origin ou absent (client non navigateur)", () => {
    expect(isSameOriginRequest("PUT", hdrs({}), APP)).toBe(true)
    expect(isSameOriginRequest("PUT", hdrs({ "sec-fetch-site": "same-origin" }), APP)).toBe(true)
    expect(isSameOriginRequest("PUT", hdrs({ "sec-fetch-site": "same-site" }), APP)).toBe(false)
    expect(isSameOriginRequest("PUT", hdrs({ "sec-fetch-site": "cross-site" }), APP)).toBe(false)
    expect(isSameOriginRequest("PUT", hdrs({ "sec-fetch-site": "none" }), APP)).toBe(false)
  })
})
