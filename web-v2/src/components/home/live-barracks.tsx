import { Fragment, type ReactNode } from "react"
import { Avatar } from "@/components/ui/avatar"
import { Panel } from "@/components/ui/panel"
import { LiveDot, SectionHeading } from "@/components/ui/section-heading"
import type { CurvePoint, LiveFeed, LiveFeedItem, LiveState } from "@/lib/api/types"
import { formatAgo, formatClock, formatNumber } from "@/lib/format"

const CURVE_W = 250
const CURVE_H = 44
const CURVE_PAD = 4

type CurvePaths = {
  /** Un tracé par suite d'heures relevées : une heure sans relevé coupe la courbe. */
  lines: string[]
  areas: string[]
  /** Heures isolées (sans voisine relevée), dessinées en point. */
  dots: Array<{ x: number; y: number }>
}

/** Tracés SVG de la courbe 24 h ; aucune valeur n'est inventée pour une heure `null`. */
export function buildCurvePaths(points: CurvePoint[]): CurvePaths {
  const values = points.map(p => p.online).filter((v): v is number => v !== null)
  const max = Math.max(1, ...values)
  const step = points.length > 1 ? CURVE_W / (points.length - 1) : 0
  const xy = (i: number, v: number) => ({
    x: Math.round(i * step * 10) / 10,
    y: Math.round((CURVE_H - CURVE_PAD - (v / max) * (CURVE_H - 2 * CURVE_PAD)) * 10) / 10,
  })

  const runs: Array<Array<{ x: number; y: number }>> = []
  let run: Array<{ x: number; y: number }> = []
  points.forEach((p, i) => {
    if (p.online === null) {
      if (run.length) runs.push(run)
      run = []
    } else {
      run.push(xy(i, p.online))
    }
  })
  if (run.length) runs.push(run)

  const out: CurvePaths = { lines: [], areas: [], dots: [] }
  for (const r of runs) {
    if (r.length === 1) {
      out.dots.push(r[0])
      continue
    }
    const line = `M${r.map(p => `${p.x} ${p.y}`).join(" L")}`
    out.lines.push(line)
    out.areas.push(`${line} L${r[r.length - 1].x} ${CURVE_H} L${r[0].x} ${CURVE_H}Z`)
  }
  return out
}

const parisHour = new Intl.DateTimeFormat("fr-FR", { hour: "numeric", hourCycle: "h23", timeZone: "Europe/Paris" })

/** Heure (Paris) du pic de connectés sur la courbe, `null` sans aucun relevé. */
function peakHour(points: CurvePoint[]): string | null {
  let best: CurvePoint | null = null
  for (const p of points) if (p.online !== null && (best === null || p.online > (best.online ?? 0))) best = p
  // `format` seul donne déjà « 21 h » en fr-FR : on ne garde que le nombre pour maîtriser le libellé.
  const hour = best && parisHour.formatToParts(new Date(best.hour)).find(p => p.type === "hour")?.value
  return hour ? `${Number(hour)} h` : null
}

function OnlineCurve({ points }: { points: CurvePoint[] }) {
  const { lines, areas, dots } = buildCurvePaths(points)
  if (!lines.length && !dots.length) return <small className="text-xs text-muted">Pas encore de relevé sur 24 h.</small>
  return (
    <svg
      viewBox={`0 0 ${CURVE_W} ${CURVE_H}`}
      width="100%"
      height={CURVE_H}
      role="img"
      aria-label="Courbe des membres en ligne sur 24 heures"
      preserveAspectRatio="none"
      data-testid="online-curve"
    >
      <defs>
        <linearGradient id="online-curve-fill" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stopColor="#9B6BFF" stopOpacity=".4" />
          <stop offset="1" stopColor="#9B6BFF" stopOpacity="0" />
        </linearGradient>
      </defs>
      {areas.map(d => (
        <path key={`a${d}`} d={d} fill="url(#online-curve-fill)" />
      ))}
      {lines.map(d => (
        <path key={`l${d}`} d={d} stroke="#9B6BFF" strokeWidth="2" fill="none" vectorEffect="non-scaling-stroke" data-curve-line />
      ))}
      {dots.map(p => (
        <circle key={`${p.x}-${p.y}`} cx={p.x} cy={p.y} r="2" fill="#9B6BFF" data-curve-dot />
      ))}
    </svg>
  )
}

function StatCard({ label, value, highlight, children }: { label: string; value: number; highlight?: boolean; children?: ReactNode }) {
  return (
    <Panel highlight={highlight} className="grid content-start gap-2.5 px-6 py-[22px]">
      <span className="text-[15px] font-medium text-muted">{label}</span>
      <span className="font-display text-[52px] leading-none font-extrabold tracking-[-0.03em] tabular-nums">
        {formatNumber(value)}
      </span>
      {children}
    </Panel>
  )
}

function feedText(item: LiveFeedItem): string {
  return item.type === "achievement" ? `${item.username} débloque « ${item.label} »` : `${item.username} : ${item.label}`
}

const FEED_SHOWN = 4

function ActivityTicker({ items, now }: { items: LiveFeedItem[]; now: Date }) {
  const shown = items.slice(0, FEED_SHOWN)
  return (
    <ul
      className="m-0 mt-6 flex list-none flex-wrap items-center gap-3 rounded-[14px] border border-white/6 bg-[rgb(19_22_42/0.7)] px-[18px] py-3 text-[13px] font-medium"
      aria-label="Activité récente"
    >
      {shown.map((item, i) => (
        <Fragment key={`${item.user_id}-${item.at}-${i}`}>
          {i > 0 && <li aria-hidden="true" className="size-1 rounded-full bg-muted" />}
          <li className="flex flex-wrap items-center gap-3">
            <em className="font-semibold text-cyan not-italic">{formatAgo(item.at, now)}</em>
            <span>{feedText(item)}</span>
          </li>
        </Fragment>
      ))}
    </ul>
  )
}

const AVATARS_SHOWN = 5

type LiveBarracksProps = {
  /** `null` : aucune donnée (API muette, aucun relevé) → section masquée. */
  live: LiveState | null
  feed: LiveFeed | null
  now: Date
}

export function LiveBarracks({ live, feed, now }: LiveBarracksProps) {
  if (!live) return null
  const peak = peakHour(live.curve_24h)
  const avatars = live.voice_avatars.slice(0, AVATARS_SHOWN)

  return (
    <section className="relative scroll-mt-[70px] py-24" id="communaute" aria-labelledby="caserne-title">
      <div className="pointer-events-none absolute inset-0 overflow-x-clip" aria-hidden="true">
        <div className="halo" style={{ left: "26%", top: 140, width: 700, height: 380, background: "rgb(155 107 255 / 0.14)" }} />
      </div>
      <div className="relative mx-auto max-w-[1440px] px-6 min-[1100px]:px-20">
        <SectionHeading
          id="caserne-title"
          title="La caserne en direct"
          sub="Pas de chiffres gonflés : Hermes compte les troupes en temps réel. Même ceux qui dorment en vocal."
          lead={
            live.stale ? (
              <LiveDot color="var(--color-orange)">
                Dernier relevé à {formatClock(live.updated_at)}, Hermes reprend son souffle
              </LiveDot>
            ) : (
              <LiveDot>En direct, chiffres fournis par Hermes</LiveDot>
            )
          }
        />

        <div className="mt-14 grid grid-cols-4 gap-5 max-[1000px]:grid-cols-2 max-[560px]:grid-cols-1">
          <StatCard label="Membres" value={live.members}>
            <small className="text-xs text-muted">Recensés un par un, sans tricher.</small>
          </StatCard>
          <StatCard label="En ligne maintenant" value={live.online} highlight>
            <OnlineCurve points={live.curve_24h} />
            {peak && <small className="text-xs text-muted">Pic à {peak} sur les dernières 24 heures</small>}
          </StatCard>
          <StatCard label="En vocal" value={live.in_voice}>
            {avatars.length > 0 && (
              <div className="flex" data-testid="voice-avatars">
                {avatars.map((src, i) => (
                  <Avatar
                    key={`${src}-${i}`}
                    name="Membre en vocal"
                    src={src}
                    size={30}
                    className="-mr-2 shadow-[0_0_0_2px_var(--color-panel)]"
                  />
                ))}
              </div>
            )}
            <small className="text-xs text-muted">
              {live.in_voice > 0 ? "Certains dorment, on ne juge pas." : "Silence radio. La cantine est vide."}
            </small>
          </StatCard>
          <StatCard label="Messages aujourd’hui" value={live.messages_today}>
            <small className="text-[13px] text-orange">Hermes les a tous lus. Même les « gg ».</small>
          </StatCard>
        </div>

        {feed && feed.items.length > 0 && <ActivityTicker items={feed.items} now={now} />}
      </div>
    </section>
  )
}
