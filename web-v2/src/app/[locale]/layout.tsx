import type { Metadata } from "next"
import { notFound } from "next/navigation"
import { hasLocale, NextIntlClientProvider } from "next-intl"
import { Footer } from "@/components/layout/footer"
import { Navbar } from "@/components/layout/navbar"
import { routing } from "@/i18n/routing"
import { getPublicSettings } from "@/lib/api/server"
import { fontVariables } from "../fonts"
import "../globals.css"

export const metadata: Metadata = {
  title: "SaucisseLand",
}

export default async function LocaleLayout({
  children,
  params,
}: {
  children: React.ReactNode
  params: Promise<{ locale: string }>
}) {
  const { locale } = await params
  if (!hasLocale(routing.locales, locale)) notFound()
  // Réglages publics : `null` (API muette) masque « Rejoindre Discord » ; le pied de page renvoie alors
  // « Contacter le staff » vers l'état-major. Même requête que l'accueil, dédupliquée par le cache Next.
  const settings = await getPublicSettings()

  return (
    <html lang={locale} className={fontVariables}>
      <body className="min-h-screen antialiased">
        <NextIntlClientProvider>
          <Navbar inviteUrl={settings?.invite_url ?? null} />
          {children}
          <Footer ticketPanelUrl={settings?.ticket_panel_url ?? null} />
        </NextIntlClientProvider>
      </body>
    </html>
  )
}
