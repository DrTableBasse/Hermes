// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

vi.mock("server-only", () => ({}))

const cookieJar = vi.hoisted(() => new Map<string, string>())
vi.mock("next/headers", () => ({
  cookies: async () => ({ get: (name: string) => (cookieJar.has(name) ? { value: cookieJar.get(name) } : undefined) }),
}))

const getSessionUser = vi.hoisted(() => vi.fn())
vi.mock("@/lib/api/server", () => ({ getSessionUser }))

import { adminGate } from "@/lib/admin-gate"
import { ADMIN_SECTIONS, adminEntryHref, allowedSections, hasAdminAccess } from "@/lib/admin-sections"
import { PERMISSIONS } from "@/lib/permissions"

const member = (permissions: string[]) => ({ user_id: "100", is_admin: false, is_redacteur: false, permissions })

beforeEach(() => cookieJar.set("better-auth.session_token", "tok"))
afterEach(() => {
  cookieJar.clear()
  vi.clearAllMocks()
})

describe("adminGate(permission)", () => {
  it("session munie du droit → ok, avec le jeton et les droits", async () => {
    getSessionUser.mockResolvedValue(member(["moderation.view", "tickets.manage"]))
    expect(await adminGate("moderation.view")).toEqual({
      kind: "ok",
      token: "tok",
      permissions: ["moderation.view", "tickets.manage"],
    })
    expect(getSessionUser).toHaveBeenCalledWith("tok")
  })

  it("session sans le droit → accès refusé, droit manquant nommé", async () => {
    getSessionUser.mockResolvedValue(member(["tickets.manage"]))
    expect(await adminGate("moderation.view")).toEqual({ kind: "forbidden", permission: "moderation.view" })
  })

  it("un autre droit, même large, ne remplace pas celui demandé", async () => {
    const all = Object.keys(PERMISSIONS).filter(k => k !== "settings.manage")
    getSessionUser.mockResolvedValue(member(all))
    expect((await adminGate("settings.manage")).kind).toBe("forbidden")
  })

  it("visiteur sans session → connexion, sans appel à l’API", async () => {
    cookieJar.clear()
    expect(await adminGate("moderation.view")).toEqual({ kind: "signin" })
    expect(getSessionUser).not.toHaveBeenCalled()
  })

  it("API muette → vérification impossible, pas un faux refus", async () => {
    getSessionUser.mockResolvedValue(null)
    expect(await adminGate("moderation.view")).toEqual({ kind: "unavailable" })
  })

  it("réponse sans `permissions` (ancienne API) → aucun droit", async () => {
    getSessionUser.mockResolvedValue({ user_id: "100", is_admin: false, is_redacteur: false })
    expect((await adminGate("admin.view")).kind).toBe("forbidden")
  })

  it("sans argument (cadre) : ok dès qu’une section est ouverte, refus sinon", async () => {
    getSessionUser.mockResolvedValue(member(["moderation.view"]))
    expect((await adminGate()).kind).toBe("ok")
    getSessionUser.mockResolvedValue(member(["articles.write", "articles.publish"]))
    expect(await adminGate()).toEqual({ kind: "forbidden" })
  })
})

describe("sections de l’administration", () => {
  it("chaque section exige un droit du catalogue ; la vue d’ensemble exige admin.view, Accès permissions.manage", () => {
    for (const s of ADMIN_SECTIONS) expect(Object.hasOwn(PERMISSIONS, s.permission)).toBe(true)
    expect(ADMIN_SECTIONS.find(s => s.href === "/admin")?.permission).toBe("admin.view")
    expect(ADMIN_SECTIONS.find(s => s.href === "/admin/acces")?.permission).toBe("permissions.manage")
  })

  it("seules les sections autorisées sont listées, dans l’ordre", () => {
    expect(allowedSections(["content.edit"]).map(s => s.href)).toEqual(["/admin/etat-major", "/admin/contenus"])
    expect(allowedSections([])).toEqual([])
    expect(allowedSections(Object.keys(PERMISSIONS))).toHaveLength(ADMIN_SECTIONS.length)
  })

  it("droits d’articles seuls : pas d’accès à l’administration", () => {
    expect(hasAdminAccess(["articles.write", "articles.publish"])).toBe(false)
    expect(hasAdminAccess(["analytics.view"])).toBe(true)
  })

  it("lien « Admin » : vue d’ensemble si admin.view, sinon première section ouverte", () => {
    expect(adminEntryHref(["admin.view", "tickets.manage"])).toBe("/admin")
    expect(adminEntryHref(["tickets.manage", "moderation.view"])).toBe("/admin/moderation")
    expect(adminEntryHref(["articles.write"])).toBeNull()
  })
})
