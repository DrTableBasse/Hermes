import { NextRequest, NextResponse } from "next/server"
import createIntlMiddleware from "next-intl/middleware"
import { routing } from "./i18n/routing"

const intlMiddleware = createIntlMiddleware(routing)

const PROTECTED = ["/admin", "/profile", "/editor"]

export default function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl
  const pathWithoutLocale = pathname.replace(/^\/(fr|en)/, "") || "/"

  if (PROTECTED.some(p => pathWithoutLocale.startsWith(p))) {
    const hasSession = request.cookies.has("better-auth.session_token")
    if (!hasSession) {
      const locale = pathname.split("/")[1] || "fr"
      return NextResponse.redirect(new URL(`/${locale}`, request.url))
    }
  }

  return intlMiddleware(request)
}

export const config = {
  matcher: ["/((?!api|_next|_vercel|.*\\..*).*)"],
}
