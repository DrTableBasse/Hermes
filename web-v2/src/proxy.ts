import { NextRequest, NextResponse } from "next/server"
import createIntlMiddleware from "next-intl/middleware"
import { routing } from "./i18n/routing"

const intlMiddleware = createIntlMiddleware(routing)

const PROTECTED = ["/admin", "/profil", "/editeur"]
const SESSION_COOKIES = ["better-auth.session_token", "__Secure-better-auth.session_token"]

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl
  const pathWithoutLocale = pathname.replace(/^\/fr(?=\/|$)/, "") || "/"

  const isProtected = PROTECTED.some(
    p => pathWithoutLocale === p || pathWithoutLocale.startsWith(`${p}/`)
  )
  if (isProtected && !SESSION_COOKIES.some(name => request.cookies.has(name))) {
    return NextResponse.redirect(new URL("/", request.url))
  }

  return intlMiddleware(request)
}

export const config = {
  matcher: ["/((?!api|_next|_vercel|.*\\..*).*)"],
}
