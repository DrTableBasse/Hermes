import type { ReactNode } from "react"
import { cn } from "@/lib/cn"

type SectionHeadingProps = {
  title: ReactNode
  /** Texte d'introduction sous le titre. */
  sub?: ReactNode
  /** Indicateur au-dessus du titre (pastille « en direct », statut) ; jamais une étiquette en capitales. */
  lead?: ReactNode
  /** Action alignée à droite (lien « Voir tout »). */
  action?: ReactNode
  as?: "h1" | "h2"
  id?: string
  className?: string
}

export function SectionHeading({ title, sub, lead, action, as: Tag = "h2", id, className }: SectionHeadingProps) {
  return (
    <div className={cn("flex flex-wrap items-end justify-between gap-6", className)}>
      <div>
        {lead}
        <Tag
          id={id}
          className="my-3 font-display text-[clamp(38px,4.6vw,56px)] leading-none font-extrabold tracking-[-0.03em] text-balance"
        >
          {title}
        </Tag>
        {sub && <p className="m-0 max-w-[62ch] text-lg text-muted">{sub}</p>}
      </div>
      {action}
    </div>
  )
}

/** Pastille de statut vivant (point lumineux + libellé). */
export function LiveDot({ children, color = "var(--color-green)" }: { children: ReactNode; color?: string }) {
  return (
    <span className="inline-flex items-center gap-2 text-sm font-medium" style={{ color }}>
      <i className="size-2 rounded-full bg-current shadow-[0_0_8px_currentColor]" aria-hidden="true" />
      {children}
    </span>
  )
}
