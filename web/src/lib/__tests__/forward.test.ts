import { describe, expect, it } from "vitest"
import { clientIp, sessionCookie, sessionFromCookieHeader } from "@/lib/api/forward"

const hdrs = (o: Record<string, string>) => new Headers(o)

describe("clientIp", () => {
  const preload = { HERMES_CLIENT_IP_PRELOAD: "socket" }

  it("lit x-client-ip seulement quand runtime/client-ip.cjs l'a posé", () => {
    expect(clientIp(hdrs({ "x-client-ip": " 203.0.113.9 " }), preload)).toBe("203.0.113.9")
    expect(clientIp(hdrs({ "x-client-ip": "203.0.113.9" }), {})).toBeNull()
    expect(clientIp(hdrs({}), preload)).toBeNull()
  })

  it("n'utilise jamais X-Real-IP ni X-Forwarded-For (choisis par le client)", () => {
    const spoofed = hdrs({ "x-real-ip": "1.2.3.4", "x-forwarded-for": "5.5.5.5, 6.6.6.6" })
    expect(clientIp(spoofed, preload)).toBeNull()
    expect(clientIp(spoofed, {})).toBeNull()
  })
})

describe("cookie de session", () => {
  it("lit les deux noms posés par BetterAuth", () => {
    expect(sessionFromCookieHeader("a=1; better-auth.session_token=t1")).toBe("t1")
    expect(sessionFromCookieHeader("__Secure-better-auth.session_token=t2.s%3D")).toBe("t2.s%3D")
    expect(sessionFromCookieHeader("a=1")).toBeNull()
    expect(sessionFromCookieHeader(null)).toBeNull()
  })

  it("renvoie toujours le nom lu par web-api", () => {
    expect(sessionCookie("t")).toBe("better-auth.session_token=t")
  })
})
