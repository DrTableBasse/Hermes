import { betterAuth } from "better-auth"
import { Pool } from "pg"

const pool = new Pool({
  host:     process.env.PG_HOST,
  port:     parseInt(process.env.PG_PORT ?? "5432"),
  database: process.env.PG_DB,
  user:     process.env.PG_USER,
  password: process.env.PG_PASSWORD,
})

const DISCORD_API        = "https://discord.com/api/v10"
const GUILD_ID           = process.env.GUILD_ID ?? ""
const BOT_TOKEN          = process.env.DISCORD_TOKEN ?? ""
const ADMIN_ROLE_NAME    = process.env.ADMIN_ROLE_NAME ?? "Administration"
const REDACTEUR_ROLE_NAME = process.env.REDACTEUR_ROLE_NAME ?? "rédacteur"

let _guildRoles: Record<string, string> = {}
let _guildRolesLoadedAt = 0
let _guildRolesPromise: Promise<void> | null = null
const GUILD_ROLES_TTL_MS = 10 * 60 * 1000

function loadGuildRoles(): Promise<void> {
  if (Date.now() - _guildRolesLoadedAt < GUILD_ROLES_TTL_MS && _guildRolesLoadedAt > 0) {
    return Promise.resolve()
  }
  if (_guildRolesPromise) return _guildRolesPromise
  _guildRolesPromise = (async () => {
    if (!BOT_TOKEN || !GUILD_ID) return
    try {
      const res = await fetch(`${DISCORD_API}/guilds/${GUILD_ID}/roles`, {
        headers: { Authorization: `Bot ${BOT_TOKEN}` },
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

async function resolveDiscordRoles(discordId: string): Promise<[boolean, boolean]> {
  await loadGuildRoles()
  try {
    const res = await fetch(`${DISCORD_API}/guilds/${GUILD_ID}/members/${discordId}`, {
      headers: { Authorization: `Bot ${BOT_TOKEN}` },
    })
    if (!res.ok) return [false, false]
    const member = (await res.json()) as { roles: string[] }
    const roleNames = new Set(member.roles.map(id => _guildRoles[id] ?? ""))
    const isAdmin     = roleNames.has(ADMIN_ROLE_NAME)
    const isRedacteur = roleNames.has(REDACTEUR_ROLE_NAME) || isAdmin
    return [isAdmin, isRedacteur]
  } catch {
    return [false, false]
  }
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
      mapProfileToUser: async (profile: Record<string, unknown>) => {
        const discordId = profile.id as string
        const username  = (profile.global_name as string | undefined) ?? (profile.username as string)
        const avatarHash = profile.avatar as string | undefined
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

        return { name: username, image: avatar, discordId, isAdmin, isRedacteur }
      },
    },
  },
})

export type Session = typeof auth.$Infer.Session
