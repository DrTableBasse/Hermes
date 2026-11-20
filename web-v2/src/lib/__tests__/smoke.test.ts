import { describe, expect, it } from "vitest"
import { routing } from "@/i18n/routing"

describe("smoke", () => {
  it("expose uniquement la locale fr, sans préfixe par défaut", () => {
    expect(routing.locales).toEqual(["fr"])
    expect(routing.defaultLocale).toBe("fr")
    expect(routing.localePrefix).toBe("as-needed")
  })
})
