import { NextRequest, NextResponse } from 'next/server'

const WEB_API = process.env.WEB_API_INTERNAL_URL ?? 'http://web-api:8000'

async function proxy(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  const { path } = await params
  const url = `${WEB_API}/${path.join('/')}${req.nextUrl.search}`

  const fwdHeaders: Record<string, string> = {}
  const cookie      = req.headers.get('cookie')
  const contentType = req.headers.get('content-type')
  if (cookie)      fwdHeaders['cookie']       = cookie
  if (contentType) fwdHeaders['content-type'] = contentType
  // IP du visiteur pour le rate limiting de web-api. On ne relaie jamais un
  // en-tête X-Client-IP venu du navigateur : on le reconstruit ici.
  // X-Real-IP est posé par le reverse proxy (Nginx Proxy Manager) ; à défaut,
  // on prend la dernière entrée de X-Forwarded-For, la seule ajoutée par lui.
  const xff      = req.headers.get('x-forwarded-for')
  const clientIp = req.headers.get('x-real-ip') ?? xff?.split(',').pop()?.trim()
  if (clientIp) fwdHeaders['x-client-ip'] = clientIp

  const init: RequestInit & { duplex?: string } = {
    method:  req.method,
    headers: fwdHeaders,
  }
  if (req.method !== 'GET' && req.method !== 'HEAD') {
    init.body   = req.body
    init.duplex = 'half'
  }

  const upstream = await fetch(url, init)

  const resHeaders = new Headers()
  const resContentType = upstream.headers.get('content-type')
  if (resContentType) resHeaders.set('content-type', resContentType)
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
