import { describe, expect, it } from "vitest"
import { isStaging, siteUrl } from "@/lib/site"

const env = (vars: Record<string, string>) => vars as unknown as NodeJS.ProcessEnv

describe("siteUrl", () => {
  it("retire la barre finale", () => {
    expect(siteUrl(env({ NEXT_PUBLIC_APP_URL: "https://saucisseland.fr/" }))).toBe("https://saucisseland.fr")
  })
  it("retombe sur BETTER_AUTH_URL puis sur localhost", () => {
    expect(siteUrl(env({ BETTER_AUTH_URL: "https://a.fr" }))).toBe("https://a.fr")
    expect(siteUrl(env({}))).toBe("http://localhost:3002")
  })
})

describe("isStaging", () => {
  it("vrai sur le port 3002, lu dans l'une ou l'autre variable", () => {
    expect(isStaging(env({ NEXT_PUBLIC_APP_URL: "http://192.168.10.62:3002" }))).toBe(true)
    expect(isStaging(env({ BETTER_AUTH_URL: "http://localhost:3002" }))).toBe(true)
    expect(isStaging(env({}))).toBe(true)
  })
  it("faux sur l'URL de production, même égale à WEB_V2_URL", () => {
    expect(
      isStaging(env({ NEXT_PUBLIC_APP_URL: "https://saucisseland.fr", WEB_V2_URL: "https://saucisseland.fr" })),
    ).toBe(false)
  })
})
