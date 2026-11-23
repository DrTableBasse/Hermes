import type { CSSProperties, ReactNode } from "react"
import { cn } from "@/lib/cn"

type MarqueeProps = {
  items: ReactNode[]
  /**
   * Contenu de la copie, à la place de `items`. Fourni, la copie reste cliquable (pas `inert`) :
   * l'appelant la sort lui-même de la tabulation (`tabIndex={-1}`). Sert aux vignettes qui ouvrent
   * un aperçu, dont la moitié visible du défilé serait sinon morte au clic.
   */
  copy?: ReactNode[]
  /** Défile de gauche à droite. */
  reverse?: boolean
  /** Durée d'un tour complet, en secondes. */
  speed?: number
  pauseOnHover?: boolean
  className?: string
  "aria-label"?: string
}

/**
 * Bandeau qui défile en continu. Le contenu est rendu deux fois : la piste glisse de la moitié de sa
 * largeur puis reboucle. La copie est cachée aux lecteurs d'écran et sortie de l'ordre de tabulation.
 * Sous `prefers-reduced-motion`, l'animation s'arrête et le bandeau se fait défiler à la main.
 */
export function Marquee({
  items,
  copy,
  reverse = false,
  speed = 45,
  pauseOnHover = true,
  className,
  "aria-label": ariaLabel,
}: MarqueeProps) {
  const trackStyle: CSSProperties = {
    animationDuration: `${speed}s`,
    animationDirection: reverse ? "reverse" : "normal",
  }
  return (
    <div
      className={cn("marquee", pauseOnHover && "marquee-pause", className)}
      role={ariaLabel ? "region" : undefined}
      aria-label={ariaLabel}
      // Focusable dès qu'elle est nommée : le focus met le défilé en pause (WCAG 2.2.2), même sans
      // élément interactif dans le bandeau.
      tabIndex={ariaLabel ? 0 : undefined}
    >
      <div className="marquee-track animate-marquee" style={trackStyle} data-marquee-track>
        <div className="marquee-group" data-marquee-group>
          {items}
        </div>
        <div className="marquee-group" data-marquee-group aria-hidden="true" inert={copy ? undefined : true}>
          {copy ?? items}
        </div>
      </div>
    </div>
  )
}
