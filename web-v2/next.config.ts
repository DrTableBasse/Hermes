import type { NextConfig } from "next"
import createNextIntlPlugin from "next-intl/plugin"
import { mediaRewrites } from "./src/lib/media-rewrites"
import { securityHeaderRules } from "./src/lib/security-headers"

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts")

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
    return securityHeaderRules()
  },
}

export default withNextIntl(nextConfig)
