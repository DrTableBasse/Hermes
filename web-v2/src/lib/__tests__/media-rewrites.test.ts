import { describe, expect, it } from "vitest"
import { mediaRewrites } from "@/lib/media-rewrites"

describe("mediaRewrites", () => {
  it("relaie /media/* vers web-api, et rien d'autre", () => {
    expect(mediaRewrites("http://web-api:8000")).toEqual([
      { source: "/media/:path*", destination: "http://web-api:8000/media/:path*" },
    ])
  })

  it("sans variable : URL du réseau Docker ; barre finale retirée", () => {
    expect(mediaRewrites(undefined)).toEqual([
      { source: "/media/:path*", destination: "http://web-api:8000/media/:path*" },
    ])
    expect(mediaRewrites("")[0].destination).toBe("http://web-api:8000/media/:path*")
    expect(mediaRewrites("http://localhost:8099/")[0].destination).toBe("http://localhost:8099/media/:path*")
  })

  it("garde la CSP : la source est un chemin de même origine sous /media", () => {
    const [rule] = mediaRewrites("http://web-api:8000")
    expect(rule.source.startsWith("/media/")).toBe(true)
  })
})
