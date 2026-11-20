import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

vi.mock("server-only", () => ({}))

import {
  apiGet,
  apiGetOrNull,
  getEvents,
  getGrades,
  getLive,
  getPage,
  leaderboardLevels,
  listTags,
} from "@/lib/api/server"

const fetchMock = vi.fn()

function reply(status: number, body?: unknown): Response {
  return new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  })
}

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock)
  vi.stubEnv("WEB_API_INTERNAL_URL", "http://web-api:8000")
})

afterEach(() => {
  fetchMock.mockReset()
  vi.unstubAllGlobals()
  vi.unstubAllEnvs()
})

describe("apiGet", () => {
  it("renvoie le JSON décodé et appelle web-api en direct", async () => {
    fetchMock.mockResolvedValue(reply(200, { ok: true }))
    await expect(apiGet<{ ok: boolean }>("/ping")).resolves.toEqual({ ok: true })
    expect(fetchMock.mock.calls[0][0]).toBe("http://web-api:8000/ping")
  })

  it("lève une erreur contenant le statut sur un 500", async () => {
    fetchMock.mockResolvedValue(reply(500, { detail: "boom" }))
    await expect(apiGet("/ping")).rejects.toThrow(/500/)
  })

  it("transmet le cookie better-auth.session_token quand token est fourni", async () => {
    fetchMock.mockResolvedValue(reply(200, {}))
    await apiGet("/auth/me", { token: "abc123" })
    const init = fetchMock.mock.calls[0][1]
    expect(init.headers.Cookie).toBe("better-auth.session_token=abc123")
  })

  it("n'envoie aucun cookie sans token", async () => {
    fetchMock.mockResolvedValue(reply(200, {}))
    await apiGet("/live")
    expect(fetchMock.mock.calls[0][1].headers.Cookie).toBeUndefined()
  })

  it("applique next.revalidate quand il est demandé, no-store sinon", async () => {
    fetchMock.mockImplementation(async () => reply(200, {}))
    await apiGet("/a", { revalidate: 60 })
    await apiGet("/b")
    expect(fetchMock.mock.calls[0][1].next).toEqual({ revalidate: 60 })
    expect(fetchMock.mock.calls[0][1].cache).toBeUndefined()
    expect(fetchMock.mock.calls[1][1].cache).toBe("no-store")
  })

  it("lève une erreur sur un 204 (aucun contenu à décoder)", async () => {
    fetchMock.mockResolvedValue(reply(204))
    await expect(apiGet("/live")).rejects.toThrow(/204/)
  })
})

describe("apiGetOrNull", () => {
  it("renvoie null sur un 204", async () => {
    fetchMock.mockResolvedValue(reply(204))
    await expect(apiGetOrNull("/live")).resolves.toBeNull()
  })

  it("renvoie null quand fetch lève une exception réseau", async () => {
    fetchMock.mockRejectedValue(new TypeError("fetch failed"))
    await expect(apiGetOrNull("/live")).resolves.toBeNull()
  })

  it("renvoie null sur une réponse d'erreur HTTP", async () => {
    fetchMock.mockResolvedValue(reply(503, { detail: "indisponible" }))
    await expect(apiGetOrNull("/pages/reglement")).resolves.toBeNull()
  })

  it("renvoie null sur un corps qui n'est pas du JSON", async () => {
    fetchMock.mockResolvedValue(new Response("<html>", { status: 200 }))
    await expect(apiGetOrNull("/live")).resolves.toBeNull()
  })

  it("renvoie le JSON sur un 200", async () => {
    fetchMock.mockResolvedValue(reply(200, { items: [] }))
    await expect(apiGetOrNull("/live/feed")).resolves.toEqual({ items: [] })
  })
})

describe("fonctions nommées", () => {
  it("getLive interroge /live avec un revalidate de 30 s et gère le 204", async () => {
    fetchMock.mockResolvedValue(reply(204))
    await expect(getLive()).resolves.toBeNull()
    expect(fetchMock.mock.calls[0][0]).toBe("http://web-api:8000/live")
    expect(fetchMock.mock.calls[0][1].next).toEqual({ revalidate: 30 })
  })

  it("getEvents garde le drapeau stale optionnel", async () => {
    fetchMock.mockResolvedValue(reply(200, { events: [], stale: true }))
    await expect(getEvents()).resolves.toEqual({ events: [], stale: true })
  })

  it("getGrades déballe la clé grades", async () => {
    const grades = [{ level_min: 1, name: "Recrue Cocktail", slug: "recrue", color: "#9A97B8" }]
    fetchMock.mockResolvedValue(reply(200, { grades }))
    await expect(getGrades()).resolves.toEqual(grades)
  })

  it("getGrades renvoie null si web-api est injoignable", async () => {
    fetchMock.mockRejectedValue(new TypeError("fetch failed"))
    await expect(getGrades()).resolves.toBeNull()
  })

  it("getPage encode le slug et renvoie null sur un 404", async () => {
    fetchMock.mockResolvedValue(reply(404, { detail: "Page inconnue" }))
    await expect(getPage("mentions légales")).resolves.toBeNull()
    expect(fetchMock.mock.calls[0][0]).toBe("http://web-api:8000/pages/mentions%20l%C3%A9gales")
  })

  it("listTags déballe la clé tags", async () => {
    fetchMock.mockResolvedValue(reply(200, { tags: [{ id: 1, name: "Bot", slug: "bot", color: "#fff" }] }))
    await expect(listTags()).resolves.toHaveLength(1)
  })

  it("leaderboardLevels construit la requête paginée avec recherche encodée", async () => {
    fetchMock.mockResolvedValue(reply(200, { leaderboard: [], total: 0, page: 2, limit: 5 }))
    await leaderboardLevels(2, 5, "j&k")
    expect(fetchMock.mock.calls[0][0]).toBe(
      "http://web-api:8000/leaderboard/levels?page=2&limit=5&search=j%26k",
    )
  })

  it("une fonction non « direct » propage l'erreur HTTP", async () => {
    fetchMock.mockResolvedValue(reply(500))
    await expect(leaderboardLevels()).rejects.toThrow(/500/)
  })
})
