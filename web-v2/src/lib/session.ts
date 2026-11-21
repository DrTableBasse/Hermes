import { cookies } from "next/headers"
import { SESSION_COOKIES } from "@/lib/api/forward"

/** Jeton de session BetterAuth du visiteur, à transmettre à web-api ; `null` sans session. */
export async function sessionToken(): Promise<string | null> {
  const jar = await cookies()
  for (const name of SESSION_COOKIES) {
    const value = jar.get(name)?.value
    if (value) return value
  }
  return null
}
