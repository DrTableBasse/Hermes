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

const DISCORD_SIZES = [64, 128, 256, 512, 1024]

/**
 * Avatar du CDN Discord à la plus petite taille servie qui couvre `size` (web-api renvoie `?size=1024`,
 * bien trop lourd pour 34 px) ; toute autre URL est rendue telle quelle.
 */
export function avatarSrc(src: string, size: number): string {
  let url: URL
  try {
    url = new URL(src)
  } catch {
    return src
  }
  if (url.hostname !== "cdn.discordapp.com") return src
  url.searchParams.set("size", String(DISCORD_SIZES.find(s => s >= size) ?? 1024))
  return url.toString()
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
        // `unoptimized`, comme les autres images distantes : le navigateur lit le CDN directement (CSP
        // `img-src`), sans faire passer chaque avatar par `/_next/image` et le conteneur web.
        <Image
          src={avatarSrc(src, size)}
          alt=""
          width={size}
          height={size}
          unoptimized
          className="size-full object-cover"
        />
      ) : (
        name.trim().charAt(0).toUpperCase() || "?"
      )}
    </span>
  )
}
