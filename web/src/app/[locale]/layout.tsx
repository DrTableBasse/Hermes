import type { Metadata } from 'next'
import { headers } from 'next/headers'
import { notFound } from 'next/navigation'
import { NextIntlClientProvider } from 'next-intl'
import { getMessages } from 'next-intl/server'
import { routing } from '@/i18n/routing'
import { Navbar } from '@/components/Navbar'
import { auth } from '@/lib/auth'
import type { User } from '@/lib/api'
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

  let user: User | null = null
  try {
    const session = await auth.api.getSession({ headers: await headers() })
    if (session) {
      const u = session.user as typeof session.user & {
        discordId?: string; isAdmin?: boolean; isRedacteur?: boolean
      }
      user = {
        user_id:      u.discordId ?? "",
        username:     u.name,
        avatar:       u.image ?? null,
        is_admin:     u.isAdmin ?? false,
        is_redacteur: u.isRedacteur ?? false,
      }
    }
  } catch {}

  return (
    <html lang={locale} className="dark">
      <body>
        <NextIntlClientProvider messages={messages}>
          <Navbar user={user} locale={locale} />
          <main className="min-h-screen">{children}</main>
          <footer className="border-t border-border/40 mt-16 py-8">
            <div className="container mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-2 text-sm text-muted-foreground">
              <span>© {new Date().getFullYear()} Hermes · SaucisseLand</span>
              <span className="text-xs opacity-60">Développé avec ❤️ pour la communauté</span>
            </div>
          </footer>
        </NextIntlClientProvider>
      </body>
    </html>
  )
}
