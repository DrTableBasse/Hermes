import type { CSSProperties, ComponentProps } from "react"
import { cn } from "@/lib/cn"

type ChipProps = ComponentProps<"span"> & {
  /**
   * Couleur CSS (hex ou var(--color-…)) : fond à 14 %, bordure à 50 %, texte éclairci (60 % mêlé de
   * blanc) pour passer l'AA même avec une couleur sombre venue de l'admin (vérifié par contrast.test.ts).
   */
  color?: string
  /** Pastille « Exemple » : pointillés atténués, pour tout contenu qui n'est pas réel. */
  example?: boolean
}

export function Chip({ color = "var(--color-muted)", example, className, style, ...rest }: ChipProps) {
  if (example) {
    return (
      <span
        className={cn(
          "inline-flex items-center justify-self-start rounded-full border border-dashed border-muted/50 px-2.5 py-[3px] text-xs font-semibold text-muted",
          className,
        )}
        style={style}
        {...rest}
      />
    )
  }
  return (
    <span
      className={cn(
        "inline-flex items-center justify-self-start gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold whitespace-nowrap",
        "border-[color-mix(in_srgb,var(--c)_50%,transparent)] bg-[color-mix(in_srgb,var(--c)_14%,transparent)] text-[color-mix(in_oklab,var(--c)_60%,white)]",
        className,
      )}
      style={{ "--c": color, ...style } as CSSProperties}
      {...rest}
    />
  )
}
