import type { CSSProperties } from "react"
import { Avatar } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import { Chip } from "@/components/ui/chip"
import type { Game, StaffMember } from "@/lib/api/types"
import { formatNumber } from "@/lib/format"

type StaffCardProps = {
  member: StaffMember
  /** Jeux actifs par clé (`GET /games`) ; une clé absente n'est pas affichée. */
  games: ReadonlyMap<string, Game>
  /** Salon du panneau de tickets ; `null` : pas de bouton (la page explique comment ouvrir un ticket). */
  ticketUrl: string | null
}

const FALLBACK_COLOR = "var(--color-violet)"

/** Carte d'un gradé de l'état-major : couleur, nom et niveau du grade réel (table `grades`). */
export function StaffCard({ member, games, ticketUrl }: StaffCardProps) {
  const color = member.grade?.color ?? FALLBACK_COLOR
  const memberGames = member.games.flatMap(key => games.get(key) ?? [])

  return (
    <article
      className="grid content-start gap-3.5 rounded-[22px] border border-[color-mix(in_srgb,var(--c)_35%,transparent)] bg-[linear-gradient(160deg,color-mix(in_srgb,var(--c)_14%,transparent),rgb(19_22_42/0.92)_45%)] p-6"
      style={{ "--c": color } as CSSProperties}
      data-testid="staff-card"
    >
      <Avatar name={member.name} src={member.avatar} size={72} color={color} ring={color} />
      <div className="min-w-0">
        <h2 className="m-0 mb-1.5 font-display text-[22px] leading-tight font-bold [overflow-wrap:anywhere]">{member.name}</h2>
        {member.role && <Chip color={color}>{member.role}</Chip>}
      </div>
      {member.grade && (
        <p className="m-0 font-display font-bold text-[color-mix(in_oklab,var(--c)_70%,white)]">
          {member.grade.name}
          {member.level !== null && (
            <span className="font-sans text-sm font-semibold text-muted"> · niveau {formatNumber(member.level)}</span>
          )}
        </p>
      )}
      {member.motto && <p className="m-0 text-[15px] leading-normal text-msg [overflow-wrap:anywhere]">«&nbsp;{member.motto}&nbsp;»</p>}
      {memberGames.length > 0 && (
        <ul className="m-0 flex list-none flex-wrap gap-2 p-0" aria-label={`Jeux de ${member.name}`}>
          {memberGames.map(g => (
            <li key={g.key}>
              <Chip color={g.color}>{g.name}</Chip>
            </li>
          ))}
        </ul>
      )}
      {ticketUrl && (
        // Le panneau ouvre un ticket vers tout le staff : même lien sur chaque carte.
        <Button href={ticketUrl} variant="ghost" className="justify-self-start">
          Contacter via un ticket
        </Button>
      )}
    </article>
  )
}
