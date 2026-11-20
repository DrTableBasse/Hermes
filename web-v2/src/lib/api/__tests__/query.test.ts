import { describe, expect, it } from "vitest"

import { query, seg } from "@/lib/api/query"

describe("seg", () => {
  it("encode séparateurs, point d'interrogation et accents", () => {
    expect(seg("../admin")).toBe("..%2Fadmin")
    expect(seg("a?b=1#c")).toBe("a%3Fb%3D1%23c")
    expect(seg("é")).toBe("%C3%A9")
  })

  it("accepte un nombre", () => {
    expect(seg(42)).toBe("42")
  })
})

describe("query", () => {
  it("omet les valeurs absentes ou vides et encode les autres", () => {
    expect(query({ page: 1, search: "j&k", tag: undefined, empty: "" })).toBe("?page=1&search=j%26k")
  })

  it("renvoie une chaîne vide sans paramètre", () => {
    expect(query({})).toBe("")
  })
})
