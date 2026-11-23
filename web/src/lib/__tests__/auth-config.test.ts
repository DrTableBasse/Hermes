// @vitest-environment node
import { parseAdditionalUserInputFromProviderProfile, parseUserInput } from "better-auth/db"
import { describe, expect, it, vi } from "vitest"

vi.mock("server-only", () => ({}))

// Vrai Pool (BetterAuth en a besoin pour son adaptateur), jamais connecté : un appel à la base
// serait un échec du test.
const { pool } = await import("@/lib/db")
const query = vi.spyOn(pool, "query").mockImplementation(() => {
  throw new Error("aucun accès à la base attendu")
})
const { auth } = await import("@/lib/auth")

const ORIGIN = "http://localhost:3000"

function post(path: string, body: unknown): Request {
  return new Request(`${ORIGIN}/api/auth${path}`, {
    method:  "POST",
    headers: { "content-type": "application/json", origin: ORIGIN },
    body:    JSON.stringify(body),
  })
}

describe("BetterAuth : le membre ne peut pas écrire ses droits", () => {
  it("update-user est désactivé (404) sans toucher la base", async () => {
    query.mockClear()
    const res = await auth.handler(post("/update-user", { isAdmin: true }))
    expect(res.status).toBe(404)
    expect(query).not.toHaveBeenCalled()
  })

  it.each([
    "/update-session", "/sign-up/email", "/sign-in/email", "/change-email",
    "/change-password", "/delete-user", "/link-social", "/unlink-account",
  ])("%s, inutilisé par le site, est désactivé (404)", async (path) => {
    const res = await auth.handler(post(path, {}))
    expect(res.status).toBe(404)
  })

  it.each(["isAdmin", "isRedacteur", "sitePermissions"])(
    "%s est refusé en saisie client", (field) => {
      expect(auth.options.user.additionalFields[field as "isAdmin"].input).toBe(false)
      expect(() => parseUserInput(auth.options, { [field]: true }, "update")).toThrow(/not allowed/)
    }
  )

  it("la connexion Discord écrit toujours discordId, jamais les droits", () => {
    const data = parseAdditionalUserInputFromProviderProfile(
      auth.options, { discordId: "123", isAdmin: true, isRedacteur: true }, "create"
    )
    expect(data.discordId).toBe("123")
    expect(data.isAdmin).toBe(false)
    expect(data.isRedacteur).toBe(false)
  })
})
