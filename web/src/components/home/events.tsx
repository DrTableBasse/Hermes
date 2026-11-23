import type { CSSProperties } from "react"
import { Avatar } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import { Chip } from "@/components/ui/chip"
import { Countdown } from "@/components/ui/countdown"
import { GradeBadge } from "@/components/ui/grade-badge"
import { LiveDot, SectionHeading } from "@/components/ui/section-heading"
import type { DiscordEvent, EventsResponse } from "@/lib/api/types"
import { formatEventDay, formatEventHour, formatEventWhen, formatNumber } from "@/lib/format"

/** Teintes des pavés de date de la liste (les events Discord n'ont pas de couleur propre). */
const LIST_TINTS = ["var(--color-violet)", "var(--color-green)", "var(--color-cyan)", "var(--color-orange)"]

/** Intéressés Discord (`user_count`) ; `null` quand Discord ne le fournit pas. */
function interestedText(n: number | null): string | null {
  if (n === null) return null
  if (n === 0) return "Personne d’intéressé pour l’instant"
  return `${formatNumber(n)} ${n > 1 ? "intéressés" : "intéressé"}`
}

const xpText = (xp: number | null) => (xp === null ? null : `+${formatNumber(xp)} XP`)

function FeaturedEvent({ event }: { event: DiscordEvent }) {
  const interested = interestedText(event.user_count)
  const xp = xpText(event.xp_reward)
  const active = event.status === "active"
  return (
    <article
      className="relative grid gap-[18px] overflow-hidden rounded-3xl border border-violet/40 bg-[linear-gradient(135deg,rgb(155_107_255/0.22),rgb(19_22_42/0.92)_55%)] p-8 shadow-[0_0_50px_rgb(155_107_255/0.2)] max-[640px]:p-6"
      aria-labelledby="event-featured-title"
      data-testid="featured-event"
    >
      <div
        className="pointer-events-none absolute -top-[60px] -right-[60px] size-[260px] rounded-full bg-[radial-gradient(circle,rgb(179_32_45/0.45),transparent_70%)]"
        aria-hidden="true"
      />
      <Chip color={active ? "var(--color-green)" : "var(--color-cyan)"} className="relative text-[13px]">
        {active ? "En cours" : "Prochain event"}
      </Chip>
      <h3
        id="event-featured-title"
        className="relative m-0 font-display text-[clamp(30px,3.4vw,42px)] leading-[1.05] font-bold tracking-[-0.02em]"
      >
        {event.name}
      </h3>
      <div className="relative flex flex-wrap items-center gap-2.5 font-medium text-msg">
        <time dateTime={event.start}>{formatEventWhen(event.start)}</time>
        {event.location && (
          <>
            <span className="size-1 rounded-full bg-muted" aria-hidden="true" />
            <span>{event.location}</span>
          </>
        )}
      </div>
      {!active && <Countdown target={event.start} doneLabel="C’est parti, rejoins-nous" className="relative flex-wrap" />}
      {event.organizer && (
        <div className="relative flex flex-wrap items-center gap-3 text-sm text-msg">
          <Avatar
            name={event.organizer.name}
            src={event.organizer.avatar}
            size={38}
            ring={event.organizer.grade.color}
          />
          <span>
            Organisé par <b className="text-fg">{event.organizer.name}</b>
          </span>
          <GradeBadge grade={event.organizer.grade} />
        </div>
      )}
      {(interested || xp) && (
        <div className="relative flex flex-wrap items-center justify-between gap-4 text-sm text-msg">
          {interested && <span>{interested}</span>}
          {xp && <span className="font-display text-[15px] font-bold text-cyan">{xp} pour les participants</span>}
        </div>
      )}
      <Button href={event.url} className="relative justify-self-start px-[26px] py-3.5 text-[15px]">
        Je viens
      </Button>
    </article>
  )
}

function EventRow({ event, tint }: { event: DiscordEvent; tint: string }) {
  const day = formatEventDay(event.start)
  const interested = interestedText(event.user_count)
  const xp = xpText(event.xp_reward)
  const details = [
    formatEventHour(event.start),
    event.location,
    event.organizer && `Organisé par ${event.organizer.name}, ${event.organizer.grade.name}`,
  ].filter(Boolean)
  return (
    <li
      className="grid grid-cols-[74px_minmax(0,1fr)] items-center gap-4 rounded-[18px] border border-line bg-[rgb(19_22_42/0.85)] p-4 transition-[border-color,transform] duration-250 hover:translate-x-1 hover:border-[color-mix(in_srgb,var(--c)_55%,transparent)]"
      style={{ "--c": tint } as CSSProperties}
    >
      <time
        dateTime={event.start}
        className="rounded-[14px] border border-[color-mix(in_srgb,var(--c)_45%,transparent)] bg-[color-mix(in_srgb,var(--c)_16%,transparent)] py-2.5 text-center"
      >
        <span className="block text-xs font-semibold text-(--c)">{day.weekday}</span>
        <b className="block font-display text-[26px] leading-[1.1]">{day.day}</b>
      </time>
      <div className="min-w-0">
        <h4 className="m-0 mb-1 font-display text-lg font-bold">
          <a href={event.url} target="_blank" rel="noopener noreferrer" className="hover:text-cyan">
            {event.name}
          </a>
        </h4>
        <p className="m-0 text-[13px] text-muted">{details.join(". ")}.</p>
        {(interested || xp) && (
          <div className="mt-2 flex flex-wrap gap-x-3.5 gap-y-1.5 text-[13px] font-medium text-msg">
            {interested && <span>{interested}</span>}
            {xp && <span className="font-display font-bold text-cyan">{xp}</span>}
          </div>
        )}
      </div>
    </li>
  )
}

function EmptyEvents() {
  return (
    <div className="mt-12 grid justify-items-start gap-3 rounded-3xl border border-dashed border-white/12 bg-[rgb(19_22_42/0.6)] px-8 py-10 max-[640px]:px-6">
      <p className="m-0 font-display text-[clamp(24px,2.6vw,32px)] font-bold">Pas d’opération prévue. Repos, soldat.</p>
      <p className="m-0 max-w-[60ch] text-muted">
        Le calendrier est vide pour l’instant. Dès qu’un gradé programme un event sur Discord, il apparaît ici avec son
        compte à rebours.
      </p>
    </div>
  )
}

/** Prochains events Discord ; `null` (API muette) → section masquée, liste vide → message de repos. */
export function Events({ data }: { data: EventsResponse | null }) {
  if (!data) return null
  const events = [...data.events].sort((a, b) => Date.parse(a.start) - Date.parse(b.start))
  const [featured, ...next] = events

  return (
    <section className="relative scroll-mt-[70px] pt-10 pb-24" id="events" aria-labelledby="events-title">
      <div className="relative mx-auto max-w-[1440px] px-6 min-[1100px]:px-20">
        <SectionHeading
          id="events-title"
          title="Les prochaines manœuvres"
          sub="Soirées, tournois et build parties organisés par la commu. Tu te signales intéressé sur Discord, on te garde une place au chaud."
          lead={data.stale ? <LiveDot color="var(--color-orange)">Dernier état connu, à vérifier sur Discord</LiveDot> : undefined}
        />
        {featured ? (
          <div className="mt-12 grid grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)] gap-6 max-[1000px]:grid-cols-[minmax(0,1fr)]">
            <FeaturedEvent event={featured} />
            {next.length > 0 ? (
              <ul className="m-0 grid list-none content-start gap-3.5 p-0" aria-label="Events suivants">
                {next.map((e, i) => (
                  <EventRow key={e.id} event={e} tint={LIST_TINTS[i % LIST_TINTS.length]} />
                ))}
              </ul>
            ) : (
              <p className="m-0 self-center text-muted">Rien d’autre au programme pour l’instant. Profites-en pour t’entraîner.</p>
            )}
          </div>
        ) : (
          <EmptyEvents />
        )}
      </div>
    </section>
  )
}
