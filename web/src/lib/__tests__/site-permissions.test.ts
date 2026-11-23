// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { PERMISSIONS, computePermissions } from "@/lib/permissions"

const ALL = Object.keys(PERMISSIONS).sort()

describe("computePermissions", () => {
  it("propriétaire ou rôle admin : tous les droits", () => {
    expect(computePermissions({ isOwner: true, isAdminRole: false, roleIds: [], grants: [] })).toHaveLength(17)
    expect(computePermissions({ isOwner: false, isAdminRole: true, roleIds: [], grants: [] })).toHaveLength(17)
    expect(computePermissions({ isOwner: true, isAdminRole: true, roleIds: [], grants: [] })).toEqual(ALL)
  })

  it("union des droits des rôles du membre, sans doublon ni droit inconnu", () => {
    const grants = [{ roleId: "1", permission: "moderation.view" }, { roleId: "2", permission: "moderation.view" },
                    { roleId: "2", permission: "tickets.manage" }, { roleId: "3", permission: "articles.write" },
                    { roleId: "1", permission: "inconnu" }]
    expect(computePermissions({ isOwner: false, isAdminRole: false, roleIds: ["1", "2"], grants }))
      .toEqual(["moderation.view", "tickets.manage"])
  })

  it("rôle disparu ou aucun rôle : aucun droit", () => {
    expect(computePermissions({ isOwner: false, isAdminRole: false, roleIds: [], grants: [{ roleId: "9", permission: "admin.view" }] })).toEqual([])
  })

  it("résultat trié", () => {
    const grants = [{ roleId: "1", permission: "tickets.manage" }, { roleId: "1", permission: "admin.view" }]
    expect(computePermissions({ isOwner: false, isAdminRole: false, roleIds: ["1"], grants }))
      .toEqual(["admin.view", "tickets.manage"])
  })
})

// ─── resolveDiscordRoles / roleRefreshDeps avec fetch et pool simulés ───────────────────────────

const ADMIN_ROLE = "100"
const WRITER_ROLE = "200"
const MOD_ROLE = "300"
const OWNER = "1"

type Query = { sql: string; params: unknown[] }
const db = vi.hoisted(() => ({
  queries: [] as Array<{ sql: string; params: unknown[] }>,
  grants: [] as Array<{ discord_role_id: string; permission: string }>,
  failGrants: false,
  session: null as null | { id: string; discordId: string | null; updatedAt: Date },
}))

vi.mock("pg", () => ({
  Pool: class {
    async query(sql: string, params: unknown[] = []) {
      db.queries.push({ sql, params })
      if (sql.includes("FROM bot_settings")) return { rows: [{ key: "admin_role", value: "100" }] }
      if (sql.includes("FROM site_permissions")) {
        if (db.failGrants) throw new Error("base injoignable")
        const ids = params[0] as string[]
        return { rows: db.grants.filter(g => ids.includes(g.discord_role_id)) }
      }
      if (sql.includes("FROM session")) return { rows: db.session ? [db.session] : [] }
      return { rows: [] }
    }
  },
}))
vi.mock("better-auth", () => ({ betterAuth: () => ({}) }))

let memberRoles: Record<string, string[]> = {}
let discordDown = false
let guildDown = false

function fakeFetch(input: string | URL | Request): Promise<Response> {
  const url = String(input)
  if (discordDown) return Promise.reject(new TypeError("fetch failed"))
  if (url.endsWith("/roles")) {
    return Promise.resolve(Response.json([{ id: ADMIN_ROLE, name: "Administration" }]))
  }
  const member = url.match(/\/members\/(\d+)$/)
  if (member) {
    const roles = memberRoles[member[1]]
    return Promise.resolve(roles ? Response.json({ roles }) : new Response(null, { status: 404 }))
  }
  if (url.match(/\/guilds\/\d+$/)) {
    if (guildDown) return Promise.resolve(new Response(null, { status: 503 }))
    return Promise.resolve(Response.json({ id: "999", owner_id: OWNER }))
  }
  return Promise.resolve(new Response(null, { status: 500 }))
}

async function loadAuth() {
  vi.resetModules()
  return import("@/lib/auth")
}

const updates = () => db.queries.filter((q: Query) => q.sql.includes('UPDATE "user"'))

describe("resolveDiscordRoles", () => {
  beforeEach(() => {
    vi.stubEnv("GUILD_ID", "999")
    vi.stubEnv("DISCORD_TOKEN", "jeton")
    vi.stubGlobal("fetch", vi.fn(fakeFetch))
    db.queries = []
    db.grants = [
      { discord_role_id: WRITER_ROLE, permission: "articles.write" },
      { discord_role_id: WRITER_ROLE, permission: "articles.publish" },
      { discord_role_id: MOD_ROLE, permission: "moderation.view" },
      { discord_role_id: "404", permission: "admin.view" }, // rôle supprimé de Discord
    ]
    db.failGrants = false
    db.session = null
    memberRoles = {}
    discordDown = false
    guildDown = false
  })
  afterEach(() => {
    vi.unstubAllEnvs()
    vi.unstubAllGlobals()
  })

  it("rédacteur dérivé de articles.write", async () => {
    memberRoles = { "10": [WRITER_ROLE], "11": [MOD_ROLE] }
    const { resolveDiscordRoles } = await loadAuth()
    expect(await resolveDiscordRoles("10")).toEqual({
      isAdmin: false, isRedacteur: true, permissions: ["articles.publish", "articles.write"],
    })
    expect(await resolveDiscordRoles("11")).toEqual({
      isAdmin: false, isRedacteur: false, permissions: ["moderation.view"],
    })
    const read = db.queries.find((q: Query) => q.sql.includes("FROM site_permissions"))!
    expect(read.sql).toContain("discord_role_id::text")
    expect(read.sql).toContain("ANY($1::bigint[])")
  })

  it("rôle admin ou propriétaire du serveur : administrateur et tous les droits", async () => {
    memberRoles = { "20": [ADMIN_ROLE], [OWNER]: [] }
    const { resolveDiscordRoles } = await loadAuth()
    expect(await resolveDiscordRoles("20")).toEqual({ isAdmin: true, isRedacteur: true, permissions: ALL })
    expect(await resolveDiscordRoles(OWNER)).toEqual({ isAdmin: true, isRedacteur: true, permissions: ALL })
  })

  it("propriétaire mis en cache : un seul appel à /guilds/{id}", async () => {
    memberRoles = { [OWNER]: [], "10": [WRITER_ROLE] }
    const { resolveDiscordRoles } = await loadAuth()
    await resolveDiscordRoles(OWNER)
    await resolveDiscordRoles("10")
    await resolveDiscordRoles(OWNER)
    const guildCalls = vi.mocked(fetch).mock.calls.filter(([u]) => /\/guilds\/999$/.test(String(u)))
    expect(guildCalls).toHaveLength(1)
    const init = guildCalls[0][1] as RequestInit
    expect(init.signal).toBeInstanceOf(AbortSignal)
  })

  it("propriétaire introuvable (Discord en erreur sur /guilds) : pas de droit de propriétaire", async () => {
    guildDown = true
    memberRoles = { [OWNER]: [] }
    const { resolveDiscordRoles } = await loadAuth()
    expect(await resolveDiscordRoles(OWNER)).toEqual({ isAdmin: false, isRedacteur: false, permissions: [] })
  })

  it("membre parti du serveur : aucun droit", async () => {
    const { resolveDiscordRoles } = await loadAuth()
    expect(await resolveDiscordRoles("77")).toEqual({ isAdmin: false, isRedacteur: false, permissions: [] })
  })

  it("à la connexion, Discord injoignable : aucun droit", async () => {
    discordDown = true
    memberRoles = { "20": [ADMIN_ROLE] }
    const { resolveDiscordRoles } = await loadAuth()
    expect(await resolveDiscordRoles("20")).toEqual({ isAdmin: false, isRedacteur: false, permissions: [] })
  })

  it("store écrit isAdmin, isRedacteur et sitePermissions", async () => {
    const { roleRefreshDeps } = await loadAuth()
    await roleRefreshDeps.store("u1", { isAdmin: false, isRedacteur: true, permissions: ["articles.write"] })
    const [q] = updates()
    expect(q.sql).toContain('"isAdmin" = $1')
    expect(q.sql).toContain('"isRedacteur" = $2')
    expect(q.sql).toContain('"sitePermissions" = $3')
    expect(q.params).toEqual([false, true, ["articles.write"], "u1"])
  })

  it("Discord injoignable pendant la réévaluation : droits stockés inchangés", async () => {
    discordDown = true
    db.session = { id: "u1", discordId: "20", updatedAt: new Date(Date.now() - 60 * 60 * 1000) }
    const { roleRefreshDeps } = await loadAuth()
    const { createRoleRefresher } = await import("@/lib/role-refresh")
    expect(await roleRefreshDeps.resolve("20")).toBeNull()
    await createRoleRefresher(roleRefreshDeps)("abcdefghijklmnopqrstuvwxyz012345")
    expect(updates()).toEqual([])
  })

  it("lecture des droits en échec pendant la réévaluation : droits stockés inchangés", async () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {})
    db.failGrants = true
    memberRoles = { "10": [WRITER_ROLE] }
    db.session = { id: "u1", discordId: "10", updatedAt: new Date(Date.now() - 60 * 60 * 1000) }
    const { roleRefreshDeps } = await loadAuth()
    const { createRoleRefresher } = await import("@/lib/role-refresh")
    await createRoleRefresher(roleRefreshDeps)("abcdefghijklmnopqrstuvwxyz012345")
    expect(updates()).toEqual([])
    expect(spy).toHaveBeenCalledWith("[auth] lecture de site_permissions impossible:", expect.any(Error))
    spy.mockRestore()
  })

  it("réévaluation : le rôle retiré fait disparaître ses droits", async () => {
    memberRoles = { "10": [] }
    db.session = { id: "u1", discordId: "10", updatedAt: new Date(Date.now() - 60 * 60 * 1000) }
    const { roleRefreshDeps } = await loadAuth()
    const { createRoleRefresher } = await import("@/lib/role-refresh")
    await createRoleRefresher(roleRefreshDeps)("abcdefghijklmnopqrstuvwxyz012345")
    expect(updates().map(q => q.params)).toEqual([[false, false, [], "u1"]])
  })
})
