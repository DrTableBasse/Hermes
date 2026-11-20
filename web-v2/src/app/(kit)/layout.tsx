import { fontVariables } from "../fonts"
import "../globals.css"

/**
 * Racine nue de la page de relecture `/_kit` : ni navbar ni pied de page du site (la page monte ses
 * propres exemplaires de démonstration). Second layout racine, hors de `[locale]`.
 */
export default function KitLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr" className={fontVariables}>
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  )
}
