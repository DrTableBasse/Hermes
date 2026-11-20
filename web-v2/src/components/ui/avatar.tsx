import Image from "next/image"
import type { CSSProperties } from "react"
import { cn } from "@/lib/cn"

type AvatarProps = {
  name: string
  /** Image Discord ; sans elle, initiale sur fond `color`. */
  src?: string | null
  size?: number
  color?: string
  /** Anneau (vert = en vocal, couleur du grade sur un profil). */
  ring?: string
  /** Annonce le nom aux lecteurs d'écran ; par défaut décoratif, le nom étant affiché à côté. */
  labelled?: boolean
  className?: string
}

export function Avatar({
  name,
  src,
  size = 34,
  color = "var(--color-violet)",
  ring,
  labelled = false,
  className,
}: AvatarProps) {
  const style = {
    width: size,
    height: size,
    background: color,
    fontSize: Math.round(size * 0.42),
    boxShadow: ring ? `0 0 0 2.5px ${ring}` : undefined,
  } satisfies CSSProperties

  return (
    <span
      className={cn(
        "relative grid flex-none place-items-center overflow-hidden rounded-full font-display font-bold text-white",
        className,
      )}
      style={style}
      role={labelled ? "img" : undefined}
      aria-label={labelled ? name : undefined}
      aria-hidden={labelled ? undefined : true}
    >
      {src ? (
        <Image src={src} alt="" width={size} height={size} className="size-full object-cover" />
      ) : (
        name.trim().charAt(0).toUpperCase() || "?"
      )}
    </span>
  )
}
