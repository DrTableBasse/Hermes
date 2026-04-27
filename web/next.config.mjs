import createNextIntlPlugin from 'next-intl/plugin'

const withNextIntl = createNextIntlPlugin('./src/i18n/request.ts')

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  images: {
    remotePatterns: [
      { protocol: 'https', hostname: 'cdn.discordapp.com' },
      { protocol: 'http',  hostname: 'localhost' },
    ],
  },
}

export default withNextIntl(nextConfig)
