import { describe, expect, it } from "vitest"
import { PROXY_TIMEOUT_MS, UPLOAD_TIMEOUT_MS, proxyTimeoutFor } from "@/lib/api/forward"

describe("proxyTimeoutFor", () => {
  it("envoi multipart : délai long (10 Mo sur une liaison lente)", () => {
    expect(proxyTimeoutFor("multipart/form-data; boundary=x")).toBe(UPLOAD_TIMEOUT_MS)
    expect(proxyTimeoutFor("Multipart/Form-Data; boundary=x")).toBe(UPLOAD_TIMEOUT_MS)
  })
  it("autres requêtes : délai court", () => {
    expect(proxyTimeoutFor("application/json")).toBe(PROXY_TIMEOUT_MS)
    expect(proxyTimeoutFor(null)).toBe(PROXY_TIMEOUT_MS)
    expect(UPLOAD_TIMEOUT_MS).toBeGreaterThan(PROXY_TIMEOUT_MS)
  })
})
