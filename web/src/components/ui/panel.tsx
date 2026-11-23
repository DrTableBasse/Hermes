import type { ComponentProps, ElementType } from "react"
import { cn } from "@/lib/cn"

type PanelProps<T extends ElementType> = {
  as?: T
  /** Mise en avant : liseré et lueur violets (une seule carte par groupe). */
  highlight?: boolean
} & Omit<ComponentProps<T>, "as">

/** Carte sombre épurée, sans verre. */
export function Panel<T extends ElementType = "div">({ as, highlight, className, ...rest }: PanelProps<T>) {
  const Tag: ElementType = as ?? "div"
  return (
    <Tag
      className={cn(
        "rounded-[20px] border bg-[rgb(19_22_42/0.92)] p-6 shadow-[0_16px_30px_rgb(0_0_0/0.35)] transition-colors duration-250",
        highlight
          ? "border-violet/45 shadow-[0_0_40px_rgb(155_107_255/0.3)]"
          : "border-line hover:border-violet/35",
        className,
      )}
      {...rest}
    />
  )
}
