import { describe, expect, it } from "vitest"
import { securityHeaderRules, SITE_CSP, TRANSCRIPT_CSP } from "@/lib/security-headers"

describe("en-têtes de sécurité", () => {
  it("la transcription d'un ticket reçoit la CSP sandbox, posée après la CSP du site", () => {
    const rules = securityHeaderRules()
    const csp = (i: number) => rules[i].headers.find(x => x.key === "Content-Security-Policy")?.value
    expect(rules[0].source).toBe("/(.*)")
    expect(csp(0)).toBe(SITE_CSP)
    const last = rules.length - 1
    expect(rules[last].source).toBe("/api/proxy/tickets/:id/transcript")
    expect(csp(last)).toBe(TRANSCRIPT_CSP)
    expect(TRANSCRIPT_CSP).toMatch(/^sandbox;/)
    expect(TRANSCRIPT_CSP).not.toMatch(/script-src/)
  })
})
