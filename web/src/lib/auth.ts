import { betterAuth } from "better-auth"
import { Pool } from "pg"
import type { RoleRefreshDeps, StaffRoles } from "./role-refresh"

const pool = new Pool({
  host:     process.env.PG_HOST,
  port:     parseInt(process.env.PG_PORT ?? "5432"),
  database: process.env.PG_DB,
  user:     process.env.PG_USER,
  password: process.env.PG_PASSWORD,
  // Base injoignable : échec en 5 s plutôt qu'une attente sans fin d'une connexion libre.
  connectionTimeoutMillis: 5000,
})

const DISCORD_API        = "https://discord.com/api/v10"
const GUILD_ID           = process.env.GUILD_ID ?? ""
const BOT_TOKEN          = process.env.DISCORD_TOKEN ?? ""
const ADMIN_ROLE_NAME    = process.env.ADMIN_ROLE_NAME ?? "Administration"
const REDACTEUR_ROLE_NAME = process.env.REDACTEUR_ROLE_NAME ?? "rédacteur"

// Rôle par identifiant (réglage en base) ou par nom (repli sur l'environnement).
type RoleRef = { id: string } | { name: string }

let _guildRoles: Record<string, string> = {}
let _staffRoles: { admin: RoleRef; redacteur: RoleRef } = {
  admin:     { name: ADMIN_ROLE_NAME },
  redacteur: { name: REDACTEUR_ROLE_NAME },
}
let _guildRolesLoadedAt = 0
let _guildRolesPromise: Promise<void> | null = null
const GUILD_ROLES_TTL_MS = 10 * 60 * 1000

// Réglages admin_role / redacteur_role (identifiants) ; ligne absente → nom de l'environnement.
async function loadStaffRoles(): Promise<void> {
  try {
    const res = await pool.query<{ key: string; value: string | null }>(
      `SELECT key, value FROM bot_settings WHERE key = ANY($1::text[])`,
      [["admin_role", "redacteur_role"]]
    )
    const stored: Record<string, string> = {}
    for (const row of res.rows) if (row.value) stored[row.key] = row.value
    _staffRoles = {
      admin:     stored.admin_role     ? { id: stored.admin_role }     : { name: ADMIN_ROLE_NAME },
      redacteur: stored.redacteur_role ? { id: stored.redacteur_role } : { name: REDACTEUR_ROLE_NAME },
    }
  } catch (e) {
    console.error("[auth] lecture de bot_settings impossible, repli sur l'environnement:", e)
  }
}

function hasRole(ref: RoleRef, memberRoleIds: string[]): boolean {
  if ("id" in ref) return memberRoleIds.includes(ref.id)
  return memberRoleIds.some(id => _guildRoles[id] === ref.name)
}

function loadGuildRoles(): Promise<void> {
  if (Date.now() - _guildRolesLoadedAt < GUILD_ROLES_TTL_MS && _guildRolesLoadedAt > 0) {
    return Promise.resolve()
  }
  if (_guildRolesPromise) return _guildRolesPromise
  _guildRolesPromise = (async () => {
    await loadStaffRoles()
    if (!BOT_TOKEN || !GUILD_ID) return
    try {
      const res = await fetch(`${DISCORD_API}/guilds/${GUILD_ID}/roles`, {
        headers: { Authorization: `Bot ${BOT_TOKEN}` },
        signal: AbortSignal.timeout(5000),
      })
      if (res.ok) {
        const roles = (await res.json()) as Array<{ id: string; name: string }>
        _guildRoles = Object.fromEntries(roles.map(r => [r.id, r.name]))
        _guildRolesLoadedAt = Date.now()
      }
    } catch {}
  })().finally(() => { _guildRolesPromise = null })
  return _guildRolesPromise
}

/**
 * Rôles du membre ; `null` si Discord ne répond pas de façon exploitable (réseau, 429, 5xx, jeton
 * refusé). Un membre absent du serveur (404) n'a aucun droit.
 */
async function resolveDiscordRolesStrict(discordId: string): Promise<StaffRoles | null> {
  await loadGuildRoles()
  try {
    const res = await fetch(`${DISCORD_API}/guilds/${GUILD_ID}/members/${discordId}`, {
      headers: { Authorization: `Bot ${BOT_TOKEN}` },
      signal: AbortSignal.timeout(5000),
    })
    if (res.status === 404) return [false, false]
    if (!res.ok) return null
    const member = (await res.json()) as { roles: string[] }
    const isAdmin     = hasRole(_staffRoles.admin, member.roles)
    const isRedacteur = hasRole(_staffRoles.redacteur, member.roles) || isAdmin
    return [isAdmin, isRedacteur]
  } catch {
    return null
  }
}

/** À la connexion : sans réponse de Discord, aucun droit. */
async function resolveDiscordRoles(discordId: string): Promise<StaffRoles> {
  return (await resolveDiscordRolesStrict(discordId)) ?? [false, false]
}

/** Accès en base de `role-refresh.ts` (droits réévalués toutes les 10 minutes). */
export const roleRefreshDeps: RoleRefreshDeps = {
  async lookup(token) {
    const res = await pool.query<{ id: string; discordId: string | null; updatedAt: Date }>(
      `SELECT u.id, u."discordId", u."updatedAt"
         FROM session s JOIN "user" u ON u.id = s."userId"
        WHERE s.token = $1 AND s."expiresAt" > NOW()`,
      [token]
    )
    const row = res.rows[0]
    return row ? { userId: row.id, discordId: row.discordId, checkedAt: new Date(row.updatedAt) } : null
  },
  resolve: resolveDiscordRolesStrict,
  async store(userId, [isAdmin, isRedacteur]) {
    await pool.query(
      `UPDATE "user" SET "isAdmin" = $1, "isRedacteur" = $2, "updatedAt" = NOW() WHERE id = $3`,
      [isAdmin, isRedacteur, userId]
    )
  },
  now: () => Date.now(),
}

export const auth = betterAuth({
  database: pool,
  secret:  process.env.BETTER_AUTH_SECRET!,
  baseURL: process.env.BETTER_AUTH_URL ?? "http://localhost:3000",
  user: {
    additionalFields: {
      discordId: {
        type:     "string",
        unique:   true,
        required: false,
      },
      isAdmin: {
        type:         "boolean",
        defaultValue: false,
      },
      isRedacteur: {
        type:         "boolean",
        defaultValue: false,
      },
    },
  },
  databaseHooks: {
    session: {
      create: {
        after: async (session) => {
          try {
            const row = await pool.query<{ discordId: string }>(
              `SELECT "discordId" FROM "user" WHERE id = $1`,
              [session.userId]
            )
            const discordId = row.rows[0]?.discordId
            if (!discordId) return
            const [isAdmin, isRedacteur] = await resolveDiscordRoles(discordId)
            await pool.query(
              `UPDATE "user" SET "isAdmin" = $1, "isRedacteur" = $2, "updatedAt" = NOW() WHERE id = $3`,
              [isAdmin, isRedacteur, session.userId]
            )
          } catch (e) {
            console.error("[auth] role refresh failed:", e)
          }
        },
      },
    },
  },
  socialProviders: {
    discord: {
      clientId:     process.env.DISCORD_CLIENT_ID!,
      clientSecret: process.env.DISCORD_CLIENT_SECRET!,
      scope:        ["identify"],
      // Type DiscordProfile fourni par better-auth (inféré)
      mapProfileToUser: async (profile) => {
        const discordId = profile.id
        const username  = profile.global_name ?? profile.username
        const avatarHash = profile.avatar ?? undefined
        const avatar = avatarHash
          ? `https://cdn.discordapp.com/avatars/${discordId}/${avatarHash}.png`
          : null

        const [isAdmin, isRedacteur] = await resolveDiscordRoles(discordId)

        // Keep user_voice_data in sync for bot stats
        try {
          await pool.query(
            `INSERT INTO user_voice_data (user_id, username, discord_avatar, last_seen)
             VALUES ($1, $2, $3, NOW())
             ON CONFLICT (user_id) DO UPDATE
               SET username       = EXCLUDED.username,
                   discord_avatar = COALESCE(EXCLUDED.discord_avatar, user_voice_data.discord_avatar),
                   last_seen      = NOW(),
                   updated_at     = NOW()`,
            [discordId, username, avatar]
          )
        } catch (e) {
          console.error("[auth] user_voice_data upsert failed:", e)
        }

        return { name: username, image: avatar ?? undefined, discordId, isAdmin, isRedacteur }
      },
    },
  },
})

export type Session = typeof auth.$Infer.Session
