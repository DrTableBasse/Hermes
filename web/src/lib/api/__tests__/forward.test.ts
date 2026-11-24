import { describe, expect, it } from "vitest"
import { GAMES_TIMEOUT_MS, PROXY_TIMEOUT_MS, UPLOAD_TIMEOUT_MS, proxyTimeoutFor } from "@/lib/api/forward"

describe("proxyTimeoutFor", () => {
  it("envoi multipart : délai long (10 Mo sur une liaison lente)", () => {
    expect(proxyTimeoutFor("multipart/form-data; boundary=x", "tickets/7/reply", "POST")).toBe(UPLOAD_TIMEOUT_MS)
    expect(proxyTimeoutFor("Multipart/Form-Data; boundary=x")).toBe(UPLOAD_TIMEOUT_MS)
  })
  it("autres requêtes : délai court", () => {
    expect(proxyTimeoutFor("application/json")).toBe(PROXY_TIMEOUT_MS)
    expect(proxyTimeoutFor(null)).toBe(PROXY_TIMEOUT_MS)
    expect(UPLOAD_TIMEOUT_MS).toBeGreaterThan(PROXY_TIMEOUT_MS)
  })
  it("jeux : provision, réactivation, resync, création et désactivation → délai long", () => {
    expect(GAMES_TIMEOUT_MS).toBe(70_000)
    expect(proxyTimeoutFor("application/json", "admin/games/dbd/provision", "POST")).toBe(GAMES_TIMEOUT_MS)
    expect(proxyTimeoutFor(null, "admin/games/dbd/reactivate", "POST")).toBe(GAMES_TIMEOUT_MS)
    expect(proxyTimeoutFor("application/json", "admin/games/resync-permissions", "POST")).toBe(GAMES_TIMEOUT_MS)
    expect(proxyTimeoutFor("application/json", "admin/games", "POST")).toBe(GAMES_TIMEOUT_MS)
    expect(proxyTimeoutFor(null, "admin/games/dbd", "DELETE")).toBe(GAMES_TIMEOUT_MS)
  })
  it("jeux : lectures et édition simple → délai court", () => {
    expect(proxyTimeoutFor(null, "admin/games", "GET")).toBe(PROXY_TIMEOUT_MS)
    expect(proxyTimeoutFor(null, "admin/games/resync-permissions", "GET")).toBe(PROXY_TIMEOUT_MS)
    expect(proxyTimeoutFor("application/json", "admin/games/dbd", "PUT")).toBe(PROXY_TIMEOUT_MS)
    expect(proxyTimeoutFor(null, "admin/stats", "GET")).toBe(PROXY_TIMEOUT_MS)
  })
})
