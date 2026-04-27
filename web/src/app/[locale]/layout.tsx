import type { Metadata } from 'next'
import { notFound } from 'next/navigation'
import { NextIntlClientProvider } from 'next-intl'
import { getMessages } from 'next-intl/server'
import { routing } from '@/i18n/routing'
import { Navbar } from '@/components/Navbar'
import { api } from '@/lib/api'
import '../globals.css'

export const metadata: Metadata = {
  title: 'Hermes',
  description: 'Hub communautaire du serveur Discord',
}

export default async function LocaleLayout({
  children,
  params,
}: {
  children: React.ReactNode
  params: Promise<{ locale: string }>
}) {
  const { locale } = await params

  if (!routing.locales.includes(locale as 'fr' | 'en')) {
    notFound()
  }

  const messages = await getMessages()
  let user = null
  try {
    user = await api.auth.me()
  } catch {}

  return (
    <html lang={locale} className="dark">
      <body>
        <NextIntlClientProvider messages={messages}>
          <Navbar user={user} locale={locale} />
          <main className="min-h-screen">{children}</main>
          <footer className="border-t border-border mt-16 py-8 text-center text-sm text-muted-foreground">
            © {new Date().getFullYear()} Hermes · Développé avec ❤️
          </footer>
        </NextIntlClientProvider>
      </body>
    </html>
  )
}
