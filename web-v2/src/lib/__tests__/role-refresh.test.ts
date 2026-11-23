import { describe, expect, it, vi } from "vitest"
import { createRoleRefresher, RECHECK_MS, ROLE_TTL_MS, type RoleRefreshDeps } from "@/lib/role-refresh"

function setup(over: Partial<RoleRefreshDeps> = {}, checkedAgoMs = ROLE_TTL_MS + 1) {
  let now = 1_000_000_000
  const deps: RoleRefreshDeps = {
    lookup: vi.fn(async () => ({ userId: "u1", discordId: "42", checkedAt: new Date(now - checkedAgoMs) })),
    resolve: vi.fn(async () => [false, false] as [boolean, boolean]),
    store: vi.fn(async () => {}),
    now: () => now,
    ...over,
  }
  return {
    deps,
    refresh: createRoleRefresher(deps),
    tick: (ms: number) => {
      now += ms
    },
  }
}

describe("réévaluation des droits (TTL 10 min)", () => {
  it("retire l'admin d'une session active dont le rôle Discord a disparu", async () => {
    const { deps, refresh } = setup()
    await refresh("tok.signature")
    expect(deps.lookup).toHaveBeenCalledWith("tok")
    expect(deps.resolve).toHaveBeenCalledWith("42")
    expect(deps.store).toHaveBeenCalledWith("u1", [false, false])
  })

  it("ne recalcule pas des droits de moins de 10 minutes", async () => {
    const { deps, refresh } = setup({}, ROLE_TTL_MS - 1000)
    await refresh("tok")
    expect(deps.resolve).not.toHaveBeenCalled()
  })

  it("Discord injoignable : les droits en base sont conservés", async () => {
    const { deps, refresh } = setup({ resolve: vi.fn(async () => null) })
    await refresh("tok")
    expect(deps.store).not.toHaveBeenCalled()
  })

  it("Discord injoignable : aucune autre session ne le rappelle avant une minute", async () => {
    const { deps, refresh, tick } = setup({ resolve: vi.fn(async () => null) })
    await refresh("tok-a")
    await refresh("tok-b")
    expect(deps.resolve).toHaveBeenCalledTimes(1)
    tick(RECHECK_MS + 1)
    await refresh("tok-b")
    expect(deps.resolve).toHaveBeenCalledTimes(2)
  })

  it("au plus une lecture en base par minute et par session, appels simultanés fusionnés", async () => {
    const { deps, refresh, tick } = setup({}, 0)
    await Promise.all([refresh("tok"), refresh("tok.sig")])
    await refresh("tok")
    expect(deps.lookup).toHaveBeenCalledTimes(1)
    tick(RECHECK_MS + 1)
    await refresh("tok")
    expect(deps.lookup).toHaveBeenCalledTimes(2)
  })

  it("une erreur de base ne fait jamais échouer la requête", async () => {
    const { refresh } = setup({
      lookup: vi.fn(async () => {
        throw new Error("pg down")
      }),
    })
    const spy = vi.spyOn(console, "error").mockImplementation(() => {})
    await expect(refresh("tok")).resolves.toBeUndefined()
    spy.mockRestore()
  })
})

describe("refreshRolesInBackground", () => {
  it("rend la main tout de suite et journalise une erreur au lieu de la propager", async () => {
    vi.resetModules()
    vi.doMock("@/lib/auth", () => {
      throw new Error("auth indisponible")
    })
    const spy = vi.spyOn(console, "error").mockImplementation(() => {})
    const { refreshRolesInBackground } = await import("@/lib/role-refresh")
    expect(refreshRolesInBackground("tok")).toBeUndefined()
    await vi.waitFor(() => expect(spy).toHaveBeenCalled())
    spy.mockRestore()
    vi.doUnmock("@/lib/auth")
  })
})
