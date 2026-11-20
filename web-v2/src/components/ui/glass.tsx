import type { ComponentProps } from "react"
import { cn } from "@/lib/cn"

const tones = {
  // Barre de navigation : très translucide, flou marqué.
  nav: "rounded-[18px] border border-line bg-[rgb(21_24_41/0.6)] backdrop-blur-[24px]",
  // Fenêtres Discord : presque opaques, ombre portée profonde.
  window:
    "overflow-hidden rounded-2xl border border-white/9 bg-[rgb(20_23_42/0.94)] shadow-[0_30px_60px_rgb(0_0_0/0.55)] backdrop-blur-[20px]",
} as const

type GlassProps = ComponentProps<"div"> & { tone?: keyof typeof tones }

/** Verre dépoli. Réservé à la barre de navigation et aux fenêtres Discord. */
export function Glass({ tone = "window", className, ...rest }: GlassProps) {
  return <div className={cn(tones[tone], className)} {...rest} />
}

export const glassClass = tones
