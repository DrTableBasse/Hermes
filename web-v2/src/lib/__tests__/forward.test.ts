import { describe, expect, it } from "vitest"
import { clientIp, sessionCookie, sessionFromCookieHeader } from "@/lib/api/forward"

const hdrs = (o: Record<string, string>) => new Headers(o)

describe("clientIp", () => {
  it("préfère X-Real-IP, sinon la dernière entrée de X-Forwarded-For", () => {
    expect(clientIp(hdrs({ "x-real-ip": "1.2.3.4", "x-forwarded-for": "5.5.5.5" }))).toBe("1.2.3.4")
    expect(clientIp(hdrs({ "x-forwarded-for": "6.6.6.6, 7.7.7.7 " }))).toBe("7.7.7.7")
    expect(clientIp(hdrs({}))).toBeNull()
    expect(clientIp(hdrs({ "x-forwarded-for": " " }))).toBeNull()
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
