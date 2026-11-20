import type { CSSProperties, ReactNode } from "react"
import { Avatar } from "@/components/ui/avatar"
import { glassClass } from "@/components/ui/glass"
import { cn } from "@/lib/cn"

type DiscordWindowProps = {
  title: string
  /** Icône lucide du salon (Hash pour un salon texte, Volume2 pour un vocal). */
  icon?: ReactNode
  children: ReactNode
  className?: string
  style?: CSSProperties
}

/** Fenêtre façon Discord : en-tête du salon, corps en grille. */
export function DiscordWindow({ title, icon, children, className, style }: DiscordWindowProps) {
  return (
    <div className={cn(glassClass.window, className)} style={style}>
      <div className="flex items-center gap-2 bg-win-head px-4 py-3 text-sm font-semibold">
        {icon && <span className="flex text-muted [&_svg]:size-4" aria-hidden="true">{icon}</span>}
        {title}
      </div>
      <div className="grid gap-3.5 px-4 pt-3.5 pb-4">{children}</div>
    </div>
  )
}

type DiscordMessageProps = {
  author: string
  avatarColor?: string
  avatarSrc?: string | null
  /** Couleur du pseudo (couleur de rôle Discord). */
  nameColor?: string
  time?: string
  bot?: boolean
  children: ReactNode
}

export function DiscordMessage({
  author,
  avatarColor,
  avatarSrc,
  nameColor = "var(--color-fg)",
  time,
  bot,
  children,
}: DiscordMessageProps) {
  return (
    <div className="flex gap-3">
      <Avatar name={author} src={avatarSrc} color={avatarColor} />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 text-sm font-semibold" style={{ color: nameColor }}>
          {author}
          {bot && (
            <span className="rounded bg-blue-deep px-[5px] py-px text-[10px] font-bold text-white">BOT</span>
          )}
          {time && <time className="text-[11px] font-normal text-muted">{time}</time>}
        </div>
        <div className="mt-[3px] text-sm leading-[1.4] text-msg">{children}</div>
      </div>
    </div>
  )
}

/** Embed de bot : liseré coloré à gauche. */
export function DiscordEmbed({
  title,
  accent = "var(--color-violet)",
  children,
}: {
  title: string
  accent?: string
  children?: ReactNode
}) {
  return (
    <div
      className="mt-1.5 grid gap-2 rounded-lg border-l-4 bg-[#1E2140] px-3.5 py-3 text-[13px] text-msg"
      style={{ borderLeftColor: accent }}
    >
      <b className="font-display text-base text-fg">{title}</b>
      {children}
    </div>
  )
}
