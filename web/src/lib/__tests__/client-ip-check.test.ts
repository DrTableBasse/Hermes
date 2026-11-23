import { describe, expect, it } from "vitest"
import { CLIENT_IP_MARKER } from "@/lib/api/forward"
import { warnIfClientIpPreloadMissing } from "@/lib/client-ip-check"

describe("warnIfClientIpPreloadMissing (constat m6)", () => {
  it("avertit en production quand le marqueur du preload est absent", () => {
    const lines: string[] = []
    expect(warnIfClientIpPreloadMissing({ NODE_ENV: "production" }, l => lines.push(l))).toBe(true)
    expect(lines).toHaveLength(1)
    expect(lines[0]).toContain(CLIENT_IP_MARKER)
  })

  it("silencieux si le preload est actif, ou hors production (next dev, tests)", () => {
    const lines: string[] = []
    const warn = (l: string) => lines.push(l)
    expect(warnIfClientIpPreloadMissing({ NODE_ENV: "production", [CLIENT_IP_MARKER]: "socket" }, warn)).toBe(false)
    expect(warnIfClientIpPreloadMissing({ NODE_ENV: "development" }, warn)).toBe(false)
    expect(lines).toEqual([])
  })
})
