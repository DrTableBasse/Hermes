// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { NextRequest } from "next/server"

const h = vi.hoisted(() => ({ refresh: vi.fn<(token: string) => Promise<void>>(async () => {}) }))
vi.mock("@/lib/role-refresh", () => ({ refreshRolesInBackground: (t: string) => void h.refresh(t) }))

import { GET } from "../[...path]/route"
import { TRANSCRIPT_CSP } from "@/lib/security-headers"

const fetchMock = vi.fn()

beforeEach(() => vi.stubGlobal("fetch", fetchMock))
afterEach(() => {
  fetchMock.mockReset()
  h.refresh.mockClear()
  vi.unstubAllGlobals()
})

function call(path: string, headers: Record<string, string> = {}) {
  const req = new NextRequest(`http://localhost:3000/api/proxy/${path}`, { headers })
  return GET(req, { params: Promise.resolve({ path: path.split("/") }) })
}

const sent = () => fetchMock.mock.calls[0][1].headers as Record<string, string>

describe("route proxy vers web-api", () => {
  it("renomme le cookie __Secure- en better-auth.session_token et ne relaie que lui", async () => {
    fetchMock.mockResolvedValue(new Response("{}"))
    await call("quests", { cookie: "theme=dark; __Secure-better-auth.session_token=abc.sig" })
    expect(sent().cookie).toBe("better-auth.session_token=abc.sig")
    expect(h.refresh).toHaveBeenCalledWith("abc.sig")
  })

  it("n'attend pas la réévaluation des droits (Discord lent ou bloqué)", { timeout: 1000 }, async () => {
    h.refresh.mockImplementationOnce(() => new Promise<void>(() => {}))
    fetchMock.mockResolvedValue(new Response("{}"))
    const res = await call("quests", { cookie: "better-auth.session_token=abc.sig" })
    expect(res.status).toBe(200)
    expect(h.refresh).toHaveBeenCalledWith("abc.sig")
  })

  it("garde le cookie en HTTP et n'en pose aucun sans session", async () => {
    fetchMock.mockResolvedValue(new Response("{}"))
    await call("quests", { cookie: "better-auth.session_token=xyz" })
    expect(sent().cookie).toBe("better-auth.session_token=xyz")
    fetchMock.mockClear()
    await call("live", { cookie: "theme=dark" })
    expect(sent().cookie).toBeUndefined()
    expect(h.refresh).toHaveBeenCalledTimes(1)
  })

  it("relaie l'IP posée par le module de démarrage, jamais X-Forwarded-For ni X-Real-IP", async () => {
    vi.stubEnv("HERMES_CLIENT_IP_PRELOAD", "socket")
    fetchMock.mockResolvedValue(new Response("{}"))
    await call("live", {
      "x-client-ip": "172.18.0.1",
      "x-real-ip": "6.6.6.6",
      "x-forwarded-for": "6.6.6.6, 198.51.100.4",
    })
    expect(sent()["x-client-ip"]).toBe("172.18.0.1")
    vi.unstubAllEnvs()
  })

  it("sans module de démarrage (next dev), ne relaie aucune IP", async () => {
    fetchMock.mockResolvedValue(new Response("{}"))
    await call("live", { "x-client-ip": "6.6.6.6", "x-real-ip": "6.6.6.6" })
    expect(sent()["x-client-ip"]).toBeUndefined()
  })

  it("relaie la CSP sandbox de la transcription", async () => {
    fetchMock.mockResolvedValue(
      new Response("<p>x</p>", {
        headers: {
          "content-type": "text/html; charset=utf-8",
          "content-security-policy": TRANSCRIPT_CSP,
          "x-content-type-options": "nosniff",
          "cache-control": "private, no-store",
        },
      }),
    )
    const res = await call("tickets/7/transcript", { cookie: "better-auth.session_token=t" })
    expect(res.headers.get("content-security-policy")).toBe(TRANSCRIPT_CSP)
    expect(res.headers.get("x-content-type-options")).toBe("nosniff")
    expect(res.headers.get("cache-control")).toBe("private, no-store")
  })

  it("pose un budget de temps et répond 504 en JSON si web-api ne répond pas", async () => {
    fetchMock.mockRejectedValue(new DOMException("timeout", "TimeoutError"))
    const res = await call("admin/stats")
    expect(fetchMock.mock.calls[0][1].signal).toBeInstanceOf(AbortSignal)
    expect(res.status).toBe(504)
    expect((await res.json()).detail).toMatch(/ne répond pas/)
  })

  it("répond aussi 504 sur une erreur réseau", async () => {
    fetchMock.mockRejectedValue(new TypeError("fetch failed"))
    expect((await call("live")).status).toBe(504)
  })
})
