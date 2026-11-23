import { describe, expect, it, vi } from "vitest"
import {
  createRoleRefresher,
  MAX_INFLIGHT,
  MAX_RECENT,
  MAX_UNKNOWN,
  RECHECK_MS,
  ROLE_TTL_MS,
  UNKNOWN_TTL_MS,
  type RoleRefreshDeps,
  type StaffRoles,
} from "@/lib/role-refresh"

// Jetons au format BetterAuth (32 caractères alphanumériques).
const TOK = "a".repeat(32)
const TOK_B = "b".repeat(32)
const NONE: StaffRoles = { isAdmin: false, isRedacteur: false, permissions: [] }

function setup(over: Partial<RoleRefreshDeps> = {}, checkedAgoMs = ROLE_TTL_MS + 1) {
  let now = 1_000_000_000
  const deps: RoleRefreshDeps = {
    lookup: vi.fn(async () => ({ userId: "u1", discordId: "42", checkedAt: new Date(now - checkedAgoMs) })),
    resolve: vi.fn(async (): Promise<StaffRoles | null> => NONE),
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
    await refresh(`${TOK}.signature`)
    expect(deps.lookup).toHaveBeenCalledWith(TOK)
    expect(deps.resolve).toHaveBeenCalledWith("42")
    expect(deps.store).toHaveBeenCalledWith("u1", NONE)
  })

  it("ne recalcule pas des droits de moins de 10 minutes", async () => {
    const { deps, refresh } = setup({}, ROLE_TTL_MS - 1000)
    await refresh(TOK)
    expect(deps.resolve).not.toHaveBeenCalled()
  })

  it("Discord injoignable : les droits en base sont conservés", async () => {
    const { deps, refresh } = setup({ resolve: vi.fn(async () => null) })
    await refresh(TOK)
    expect(deps.store).not.toHaveBeenCalled()
  })

  it("Discord injoignable : aucune autre session ne le rappelle avant une minute", async () => {
    const { deps, refresh, tick } = setup({ resolve: vi.fn(async () => null) })
    await refresh(TOK)
    await refresh(TOK_B)
    expect(deps.resolve).toHaveBeenCalledTimes(1)
    tick(RECHECK_MS + 1)
    await refresh(TOK_B)
    expect(deps.resolve).toHaveBeenCalledTimes(2)
  })

  it("au plus une lecture en base par minute et par session, appels simultanés fusionnés", async () => {
    const { deps, refresh, tick } = setup({}, 0)
    await Promise.all([refresh(TOK), refresh(`${TOK}.sig`)])
    await refresh(TOK)
    expect(deps.lookup).toHaveBeenCalledTimes(1)
    tick(RECHECK_MS + 1)
    await refresh(TOK)
    expect(deps.lookup).toHaveBeenCalledTimes(2)
  })

  it("une erreur de base ne fait jamais échouer la requête", async () => {
    const { refresh } = setup({
      lookup: vi.fn(async () => {
        throw new Error("pg down")
      }),
    })
    const spy = vi.spyOn(console, "error").mockImplementation(() => {})
    await expect(refresh(TOK)).resolves.toBeUndefined()
    spy.mockRestore()
  })
})

describe("mémoire bornée et jetons invalides (constat M1)", () => {
  it("un cookie au format invalide ne déclenche aucune lecture en base", async () => {
    const { deps, refresh } = setup()
    for (const bad of ["", "tok", "x".repeat(200), "a'; DROP TABLE session;--aaaaaaaaaa", "%E0%A4%A"]) {
      await refresh(bad)
    }
    expect(deps.lookup).not.toHaveBeenCalled()
  })

  it("au-delà de MAX_RECENT sessions, les plus anciennes sont oubliées", async () => {
    const { deps, refresh } = setup({}, 0)
    const tok = (i: number) => `t${String(i).padStart(31, "0")}`
    for (let i = 0; i <= MAX_RECENT; i++) await refresh(tok(i))
    expect(deps.lookup).toHaveBeenCalledTimes(MAX_RECENT + 1)
    // La plus récente est encore mémorisée, la toute première a été oubliée.
    await refresh(tok(MAX_RECENT))
    expect(deps.lookup).toHaveBeenCalledTimes(MAX_RECENT + 1)
    await refresh(tok(0))
    expect(deps.lookup).toHaveBeenCalledTimes(MAX_RECENT + 2)
  })
})

describe("jetons inconnus et saturation (constat m5)", () => {
  const tok = (i: number) => `u${String(i).padStart(31, "0")}`

  it("un jeton inconnu répété ne coûte qu'une requête SQL par UNKNOWN_TTL_MS", async () => {
    const { deps, refresh, tick } = setup({ lookup: vi.fn(async () => null) })
    for (let i = 0; i < 5; i++) await refresh(TOK)
    tick(RECHECK_MS + 1)
    await refresh(TOK)
    expect(deps.lookup).toHaveBeenCalledTimes(1)
    tick(UNKNOWN_TTL_MS)
    await refresh(TOK)
    expect(deps.lookup).toHaveBeenCalledTimes(2)
  })

  it("un flot de jetons inconnus ne chasse pas les sessions valides", async () => {
    const lookup = vi.fn(async (t: string) =>
      t === TOK ? { userId: "u1", discordId: "42", checkedAt: new Date(1_000_000_000) } : null,
    )
    const { deps, refresh } = setup({ lookup })
    await refresh(TOK)
    for (let i = 0; i <= MAX_UNKNOWN; i++) await refresh(tok(i))
    await refresh(TOK)
    expect(deps.lookup).toHaveBeenCalledTimes(MAX_UNKNOWN + 2)
    // Cache négatif borné : le plus ancien jeton inconnu a été oublié.
    await refresh(tok(0))
    expect(deps.lookup).toHaveBeenCalledTimes(MAX_UNKNOWN + 3)
  })

  it(`au plus MAX_INFLIGHT lectures simultanées`, async () => {
    const release: Array<() => void> = []
    const lookup = vi.fn(() => new Promise<null>(resolve => release.push(() => resolve(null))))
    const { deps, refresh } = setup({ lookup })
    const calls = Array.from({ length: MAX_INFLIGHT + 20 }, (_, i) => refresh(tok(i)))
    expect(deps.lookup).toHaveBeenCalledTimes(MAX_INFLIGHT)
    release.forEach(r => r())
    await Promise.all(calls)
    // Une place libérée : une nouvelle session est de nouveau lue.
    const next = refresh(tok(MAX_INFLIGHT + 100))
    expect(deps.lookup).toHaveBeenCalledTimes(MAX_INFLIGHT + 1)
    release.at(-1)?.()
    await next
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
