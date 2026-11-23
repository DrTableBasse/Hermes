import { NextRequest, NextResponse } from 'next/server'
import {
  clientIp,
  proxyTimeoutFor,
  sessionCookie,
  sessionFromCookieHeader,
} from '@/lib/api/forward'
import { refreshRolesInBackground } from '@/lib/role-refresh'

const WEB_API = process.env.WEB_API_INTERNAL_URL ?? 'http://web-api:8000'

// En-têtes de réponse de web-api relayés au navigateur. Les en-têtes d'isolation de la
// transcription d'un ticket (CSP « sandbox ») ne doivent pas se perdre ici.
const RELAYED = [
  'content-type',
  'content-security-policy',
  'content-disposition',
  'cache-control',
  'x-content-type-options',
]

function failure(status: number, detail: string) {
  return NextResponse.json({ detail }, { status })
}

async function proxy(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  const { path } = await params
  const url = `${WEB_API}/${path.join('/')}${req.nextUrl.search}`

  const fwdHeaders: Record<string, string> = {}
  // Seul le cookie de session est relayé, sous le nom que lit web-api : en HTTPS,
  // BetterAuth le préfixe par `__Secure-`, que web-api ignorerait.
  const token = sessionFromCookieHeader(req.headers.get('cookie'))
  if (token) {
    fwdHeaders['cookie'] = sessionCookie(token)
    refreshRolesInBackground(token)
  }
  const contentType = req.headers.get('content-type')
  if (contentType) fwdHeaders['content-type'] = contentType
  // IP du visiteur pour le limiteur de web-api (même règle que le rendu serveur).
  const ip = clientIp(req.headers)
  if (ip) fwdHeaders['x-client-ip'] = ip

  const init: RequestInit & { duplex?: string } = {
    method:  req.method,
    headers: fwdHeaders,
    signal:  AbortSignal.timeout(proxyTimeoutFor(contentType)),
  }
  if (req.method !== 'GET' && req.method !== 'HEAD') {
    init.body   = req.body
    init.duplex = 'half'
  }

  let upstream: Response
  try {
    upstream = await fetch(url, init)
  } catch (e) {
    // 504 dans les deux cas : 502/503 désignent déjà le bot injoignable (adminErrorText).
    const timedOut = e instanceof Error && e.name === 'TimeoutError'
    return failure(504, timedOut ? 'Le site ne répond pas (délai dépassé).' : 'Le site ne répond pas.')
  }

  const resHeaders = new Headers()
  for (const name of RELAYED) {
    const value = upstream.headers.get(name)
    if (value) resHeaders.set(name, value)
  }
  upstream.headers.forEach((val, key) => {
    if (key.toLowerCase() === 'set-cookie') resHeaders.append('set-cookie', val)
  })

  return new NextResponse(upstream.body, {
    status:  upstream.status,
    headers: resHeaders,
  })
}

export const GET    = proxy
export const POST   = proxy
export const PUT    = proxy
export const DELETE = proxy
export const PATCH  = proxy
