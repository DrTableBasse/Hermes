/** En-têtes de sécurité du site (`next.config.ts`, `headers()`). */

type Header = { key: string; value: string }

export const SITE_CSP = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: https://cdn.discordapp.com https://i.ytimg.com",
  "connect-src 'self'",
  "font-src 'self'",
  // Lecteurs de la galerie (src/lib/gallery.ts, clipEmbedUrl), et eux seuls.
  "frame-src https://www.youtube-nocookie.com https://clips.twitch.tv https://medal.tv",
  "frame-ancestors 'none'",
].join("; ")

/**
 * Transcription d'un ticket : HTML généré à partir de messages Discord et servi sur l'origine du
 * site. « sandbox » lui donne une origine opaque (ni script, ni cookie de session), y compris pour
 * les anciennes transcriptions mal échappées. Même valeur que `web-api/routes/tickets.py`.
 */
export const TRANSCRIPT_CSP = "sandbox; default-src 'none'; style-src 'unsafe-inline'"

const securityHeaders: Header[] = [
  { key: "X-Frame-Options",        value: "DENY" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy",        value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy",     value: "camera=(), microphone=(), geolocation=()" },
  { key: "Content-Security-Policy", value: SITE_CSP },
]

/** Règles dans l'ordre de Next : pour une même clé, la dernière règle qui correspond l'emporte. */
export function securityHeaderRules(): { source: string; headers: Header[] }[] {
  return [
    { source: "/(.*)", headers: securityHeaders },
    {
      source: "/api/proxy/tickets/:id/transcript",
      headers: [{ key: "Content-Security-Policy", value: TRANSCRIPT_CSP }],
    },
  ]
}
