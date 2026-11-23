import type { Metadata } from "next"
import { notFound } from "next/navigation"
import { connection } from "next/server"
import { hasLocale, NextIntlClientProvider } from "next-intl"
import { Footer } from "@/components/layout/footer"
import { Navbar } from "@/components/layout/navbar"
import { routing } from "@/i18n/routing"
import { getPublicSettings } from "@/lib/api/server"
import { isIndexable, OG_IMAGES, siteUrl } from "@/lib/site"
import { fontVariables } from "../fonts"
import "../globals.css"

const DESCRIPTION = "SaucisseLand, la communauté Discord où Hermes compte les points, les grades et les saucisses."

export async function generateMetadata(): Promise<Metadata> {
  // Lu à chaque requête : l’URL et SITE_INDEXABLE viennent de l’environnement du conteneur, pas du build.
  await connection()
  return {
    metadataBase: new URL(siteUrl()),
    title: "SaucisseLand",
    description: DESCRIPTION,
    openGraph: { title: "SaucisseLand", description: DESCRIPTION, type: "website", locale: "fr_FR", siteName: "SaucisseLand", images: OG_IMAGES },
    twitter: { card: "summary_large_image", images: OG_IMAGES },
    // Fail-closed : sans SITE_INDEXABLE=true, aucune page n'est indexable (les pages qui définissent leur propre `robots` l'emportent).
    ...(!isIndexable() && { robots: { index: false, follow: false } }),
  }
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
