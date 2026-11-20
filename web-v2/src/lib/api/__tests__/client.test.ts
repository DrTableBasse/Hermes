import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { api, ApiError } from "@/lib/api/client"

const fetchMock = vi.fn()

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock)
})

afterEach(() => {
  fetchMock.mockReset()
  vi.unstubAllGlobals()
})

describe("client api", () => {
  it("passe par /api/proxy avec les cookies de session", async () => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify({ quests: [] }), { status: 200 }))
    await api.quests.list()
    expect(fetchMock.mock.calls[0][0]).toBe("/api/proxy/quests")
    expect(fetchMock.mock.calls[0][1].credentials).toBe("include")
  })

  it("lève une ApiError portant le statut et le detail de web-api", async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ detail: "Déjà endorsé aujourd'hui pour cette compétence" }), { status: 429 }),
    )
    const error = await api.endorsements.endorse({ target_user_id: "1", skill: "gg" }).catch((e) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect(error.status).toBe(429)
    expect(error.message).toBe("Déjà endorsé aujourd'hui pour cette compétence")
  })

  it("accepte un 204 sans corps (suppression)", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }))
    await expect(api.articles.delete(7)).resolves.toBeUndefined()
    expect(fetchMock.mock.calls[0][1].method).toBe("DELETE")
  })

  it("encode les identifiants : « ../admin » ne change pas de route", async () => {
    fetchMock.mockImplementation(async () => new Response(JSON.stringify({ warns: [] }), { status: 200 }))
    await api.admin.getWarns("../admin")
    await api.admin.updateGrade("../x", { name: "a", color: "#000000", level_min: 1 })
    await api.xp.get("a/b")
    expect(fetchMock.mock.calls[0][0]).toBe("/api/proxy/admin/warns/..%2Fadmin")
    expect(fetchMock.mock.calls[1][0]).toBe("/api/proxy/admin/grades/..%2Fx")
    expect(fetchMock.mock.calls[2][0]).toBe("/api/proxy/xp/a%2Fb")
  })

  it("envoie les identifiants Discord en chaîne dans le corps JSON", async () => {
    fetchMock.mockResolvedValue(new Response("{}", { status: 200 }))
    await api.admin.kick({ user_id: "1234567890123456789", reason: "spam" })
    expect(fetchMock.mock.calls[0][1].body).toBe('{"user_id":"1234567890123456789","reason":"spam"}')
  })
})
