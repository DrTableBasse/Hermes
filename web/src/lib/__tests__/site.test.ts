import { describe, expect, it } from "vitest"
import { isIndexable, siteUrl } from "@/lib/site"

const env = (vars: Record<string, string>) => vars as unknown as NodeJS.ProcessEnv

describe("siteUrl", () => {
  it("retire la barre finale", () => {
    expect(siteUrl(env({ NEXT_PUBLIC_APP_URL: "https://saucisseland.fr/" }))).toBe("https://saucisseland.fr")
  })
  it("retombe sur BETTER_AUTH_URL puis sur localhost", () => {
    expect(siteUrl(env({ BETTER_AUTH_URL: "https://a.fr" }))).toBe("https://a.fr")
    expect(siteUrl(env({}))).toBe("http://localhost:3000")
  })
})

describe("isIndexable (fail-closed)", () => {
  it("vrai seulement avec SITE_INDEXABLE=true", () => {
    expect(isIndexable(env({ SITE_INDEXABLE: "true" }))).toBe(true)
  })
  it("faux sans la variable, avec une autre valeur, quelle que soit l'URL", () => {
    expect(isIndexable(env({}))).toBe(false)
    expect(isIndexable(env({ SITE_INDEXABLE: "1" }))).toBe(false)
    expect(isIndexable(env({ SITE_INDEXABLE: "false" }))).toBe(false)
    expect(isIndexable(env({ NEXT_PUBLIC_APP_URL: "https://saucisseland.fr" }))).toBe(false)
    expect(isIndexable(env({ NEXT_PUBLIC_APP_URL: "http://host:3000" }))).toBe(false)
  })
})
