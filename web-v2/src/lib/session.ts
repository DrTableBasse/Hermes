import { cookies } from "next/headers"

// En HTTPS, BetterAuth préfixe son cookie par `__Secure-` (même liste que `src/proxy.ts`).
const SESSION_COOKIES = ["better-auth.session_token", "__Secure-better-auth.session_token"]

/** Jeton de session BetterAuth du visiteur, à transmettre à web-api ; `null` sans session. */
export async function sessionToken(): Promise<string | null> {
  const jar = await cookies()
  for (const name of SESSION_COOKIES) {
    const value = jar.get(name)?.value
    if (value) return value
  }
  return null
}
