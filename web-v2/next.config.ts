import type { NextConfig } from "next"
import createNextIntlPlugin from "next-intl/plugin"
import { mediaRewrites } from "./src/lib/media-rewrites"

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts")

const securityHeaders = [
  { key: "X-Frame-Options",        value: "DENY" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy",        value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy",     value: "camera=(), microphone=(), geolocation=()" },
  {
    key: "Content-Security-Policy",
    value: [
      "default-src 'self'",
      "script-src 'self' 'unsafe-inline'",
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data: https://cdn.discordapp.com https://i.ytimg.com",
      "connect-src 'self'",
      "font-src 'self'",
      // Lecteurs de la galerie (src/lib/gallery.ts, clipEmbedUrl), et eux seuls.
      "frame-src https://www.youtube-nocookie.com https://clips.twitch.tv https://medal.tv",
      "frame-ancestors 'none'",
    ].join("; "),
  },
]

const appHostname = (() => {
  try {
    return new URL(process.env.NEXT_PUBLIC_APP_URL ?? "http://localhost:3002").hostname
  } catch {
    return "localhost"
  }
})()

const nextConfig: NextConfig = {
  output: "standalone",
  images: {
    // Seules les images du volume média (galerie) passent par l'optimiseur, qui les lit à travers le
    // rewrite /media → web-api ; tout autre chemin local est refusé par /_next/image.
    localPatterns: [{ pathname: "/media/**" }],
    remotePatterns: [
      { protocol: "https", hostname: "cdn.discordapp.com" },
      { protocol: "http",  hostname: "localhost" },
      { protocol: "https", hostname: appHostname },
    ],
  },
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  async rewrites() {
    return mediaRewrites()
  },
  async headers() {
    return [{ source: "/(.*)", headers: securityHeaders }]
  },
}

export default withNextIntl(nextConfig)
