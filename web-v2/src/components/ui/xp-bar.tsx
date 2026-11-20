import type { CSSProperties } from "react"
import { cn } from "@/lib/cn"

type XpBarProps = {
  /** Avancement entre 0 et 1. */
  ratio: number
  /** Hauteur en px (8 par défaut, 10-12 sur une fiche de profil). */
  height?: number
  /** Saucisse au bout de la barre (barre d'XP d'un membre). */
  sausage?: boolean
  /** Remplissage uni (quête terminée en vert, par exemple) au lieu du dégradé violet → cyan. */
  color?: string
  label: string
  className?: string
}

export function XpBar({ ratio, height = 8, sausage = false, color, label, className }: XpBarProps) {
  const r = Number.isFinite(ratio) ? Math.min(1, Math.max(0, ratio)) : 0
  const pct = Math.round(r * 1000) / 10
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={pct}
      className={cn("relative overflow-hidden rounded-full bg-white/8", className)}
      style={{ height, "--w": `${pct}%` } as CSSProperties}
    >
      <i
        className="block h-full w-(--w) rounded-[inherit] bg-linear-to-r from-violet to-cyan"
        style={color ? { background: color } : undefined}
      />
      {sausage && (
        <svg
          className="absolute top-0 left-[clamp(0px,calc(var(--w)-14px),calc(100%-26px))] h-full w-[26px]"
          viewBox="0 0 26 10"
          aria-hidden="true"
        >
          <rect x=".5" y=".5" width="25" height="9" rx="4.5" fill="#FF8A3D" stroke="#C25A1F" />
        </svg>
      )}
    </div>
  )
}
