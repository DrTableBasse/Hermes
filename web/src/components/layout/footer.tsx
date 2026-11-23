import Link from "next/link"
import { Brand } from "@/components/layout/brand"

type FooterProps = {
  /** Salon du panneau de tickets (`ticket_panel_url` des réglages publics) ; à défaut, l'état-major. */
  ticketPanelUrl?: string | null
}

function FooterLink({ href, children }: { href: string; children: React.ReactNode }) {
  const external = /^https?:\/\//.test(href)
  const cls = "block py-1 text-sm text-muted transition-colors hover:text-fg"
  return external ? (
    <a href={href} className={cls} target="_blank" rel="noopener noreferrer">
      {children}
    </a>
  ) : (
    <Link href={href} className={cls}>
      {children}
    </Link>
  )
}

export function Footer({ ticketPanelUrl }: FooterProps) {
  const columns: Array<{ title: string; links: Array<[string, string]> }> = [
    {
      title: "Communauté",
      links: [
        ["/#jeux", "Jeux"],
        ["/galerie", "Galerie"],
        ["/etat-major", "L'état-major"],
      ],
    },
    {
      title: "Hermes",
      links: [
        ["/hermes", "Tableau de bord"],
        ["/progression", "Grades et succès"],
      ],
    },
    {
      title: "Infos",
      links: [
        ["/reglement", "Règlement"],
        ["/mentions-legales", "Mentions légales"],
        [ticketPanelUrl || "/etat-major", "Contacter le staff"],
      ],
    },
  ]

  return (
    <footer className="border-t border-line pt-12 pb-8">
      <div className="mx-auto grid max-w-[1440px] grid-cols-[minmax(0,1.4fr)_repeat(3,minmax(0,1fr))] gap-8 px-6 max-[800px]:grid-cols-2 min-[1100px]:px-20">
        <div className="max-[800px]:col-span-2">
          <Brand />
          <p className="mt-4 max-w-[36ch] text-sm text-muted">
            La communauté multi-gaming des Généraux Saucisses, propulsée par Hermes.
          </p>
        </div>
        {columns.map(col => (
          <nav key={col.title} aria-label={col.title}>
            <h2 className="mb-3 font-display text-[15px] font-bold">{col.title}</h2>
            {col.links.map(([href, label]) => (
              <FooterLink key={label} href={href}>
                {label}
              </FooterLink>
            ))}
          </nav>
        ))}
      </div>
      <p className="mx-auto mt-8 max-w-[1440px] px-6 text-[13px] text-muted min-[1100px]:px-20">
        © {new Date().getFullYear()} SaucisseLand. Aucune saucisse n&apos;a été maltraitée pendant la conception
        de ce site.
      </p>
    </footer>
  )
}
