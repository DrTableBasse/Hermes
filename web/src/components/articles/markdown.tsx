import type { ComponentProps } from "react"
import ReactMarkdown from "react-markdown"
import rehypeHighlight from "rehype-highlight"
import remarkGfm from "remark-gfm"
import { safeImageSrc } from "@/lib/articles"

const REMARK = [remarkGfm]
// `ignoreMissing` : un bloc de code dans un langage inconnu reste du texte brut au lieu de faire échouer le rendu.
const REHYPE = [[rehypeHighlight, { detect: false, ignoreMissing: true }]] as ComponentProps<typeof ReactMarkdown>["rehypePlugins"]

const COMPONENTS: ComponentProps<typeof ReactMarkdown>["components"] = {
  a({ href, children }) {
    if (!href) return <>{children}</>
    // Lien interne (chemin ou ancre) : navigation normale ; tout le reste sort du site, sans transmettre le référent.
    if (href.startsWith("/") && !href.startsWith("//")) return <a href={href}>{children}</a>
    if (href.startsWith("#")) return <a href={href}>{children}</a>
    return (
      <a href={href} target="_blank" rel="noopener noreferrer nofollow">
        {children}
      </a>
    )
  },
  img({ src, alt }) {
    const safe = typeof src === "string" ? safeImageSrc(src) : null
    // Image hors volume média / CDN Discord : bloquée par la CSP, on garde au moins son texte alternatif.
    // eslint-disable-next-line @next/next/no-img-element -- dimensions inconnues, image locale déjà optimisée
    return safe ? <img src={safe} alt={alt ?? ""} loading="lazy" /> : <span>{alt}</span>
  },
}

/**
 * Rendu Markdown d'un article : GFM + coloration du code. Le HTML brut n'est jamais interprété (pas de
 * `rehype-raw`) : react-markdown l'affiche comme du texte.
 */
export function Markdown({ children }: { children: string }) {
  return (
    <div className="prose-hermes">
      <ReactMarkdown remarkPlugins={REMARK} rehypePlugins={REHYPE} components={COMPONENTS}>
        {children}
      </ReactMarkdown>
    </div>
  )
}
