import type { Metadata } from "next"
import { OG_IMAGES } from "@/lib/site"
import { Markdown } from "@/components/articles/markdown"
import { SectionHeading } from "@/components/ui/section-heading"
import { getPage } from "@/lib/api/server"

export type LegalSlug = "reglement" | "mentions-legales"

const DEFAULTS: Record<LegalSlug, { title: string; description: string }> = {
  reglement: {
    title: "Règlement",
    description: "Le règlement de la communauté SaucisseLand : ce qui se fait, ce qui se tait, ce qui se ban.",
  },
  "mentions-legales": {
    title: "Mentions légales",
    description: "Mentions légales du site SaucisseLand : éditeur, hébergement et données personnelles.",
  },
}

/** Titre, description et indexation : une page sans texte reste hors des moteurs de recherche. */
export async function legalMetadata(slug: LegalSlug): Promise<Metadata> {
  const { title, description } = DEFAULTS[slug]
  const page = await getPage(slug)
  const published = !!page?.body_md.trim()
  return {
    title: `${title} · SaucisseLand`,
    description,
    openGraph: { title, description, type: "website", locale: "fr_FR", siteName: "SaucisseLand", images: OG_IMAGES },
    ...(!published && { robots: { index: false, follow: false } }),
  }
}

export async function LegalPage({ slug }: { slug: LegalSlug }) {
  const page = await getPage(slug)
  const body = page?.body_md.trim() ?? ""
  const title = page?.title.trim() || DEFAULTS[slug].title

  return (
    <main className="relative pt-10 pb-24">
      <div className="relative mx-auto max-w-[760px] px-6">
        <SectionHeading as="h1" title={title} />
        {body ? (
          <div className="mt-8">
            <Markdown>{body}</Markdown>
          </div>
        ) : (
          <p className="mt-8 rounded-2xl border border-line bg-[rgb(19_22_42/0.6)] px-6 py-5 text-muted" role="status">
            Bientôt. Le staff rédige ce texte, Hermes a promis de ne pas y toucher.
          </p>
        )}
      </div>
    </main>
  )
}
