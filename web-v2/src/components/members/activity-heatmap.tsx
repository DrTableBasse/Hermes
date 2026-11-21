import type { ActivityDay } from "@/lib/api/types"

const LEVELS = [
  "bg-white/6",
  "bg-green/25",
  "bg-green/50",
  "bg-green/75",
  "bg-green",
] as const

function levelOf(count: number): number {
  if (count <= 0) return 0
  if (count < 3) return 1
  if (count < 7) return 2
  if (count < 15) return 3
  return 4
}

const DAY = 86_400_000
const monthFormat = new Intl.DateTimeFormat("fr-FR", { month: "short", timeZone: "UTC" })

/** Une semaine = 7 jours, dimanche → samedi ; jours calculés en UTC, comme les dates de web-api. */
export function buildWeeks(now: Date, weeks = 52): number[][] {
  const today = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate())
  const first = today - (weeks * 7 - 1) * DAY
  const start = first - new Date(first).getUTCDay() * DAY
  const out: number[][] = []
  for (let t = start; t <= today; t += 7 * DAY) out.push(Array.from({ length: 7 }, (_, d) => t + d * DAY))
  return out
}

const key = (t: number) => new Date(t).toISOString().slice(0, 10)

/** Grille d'activité des 12 derniers mois (messages et vocal par jour). `now` est injectable pour les tests. */
export function ActivityHeatmap({ data, now = new Date() }: { data: ActivityDay[]; now?: Date }) {
  const counts = new Map(data.map(d => [d.date, d.count]))
  const weeks = buildWeeks(now)
  const today = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate())
  const cols = `28px repeat(${weeks.length}, 13px)`
  const dayLabels = ["", "Lun", "", "Mer", "", "Ven", ""]

  // Le mois s'écrit au-dessus de la première semaine où il change.
  const months = weeks.map((w, i) => {
    const m = new Date(w[0]).getUTCMonth()
    return i > 0 && m === new Date(weeks[i - 1][0]).getUTCMonth() ? "" : monthFormat.format(new Date(w[0]))
  })

  return (
    <figure className="m-0 overflow-x-auto" aria-label="Activité des 12 derniers mois">
      <div className="inline-block min-w-max">
        <div className="mb-1 grid" style={{ gridTemplateColumns: cols }} aria-hidden="true">
          <div />
          {months.map((m, i) => (
            <div key={i} className="text-[10px] text-muted">
              {m}
            </div>
          ))}
        </div>
        {[0, 1, 2, 3, 4, 5, 6].map(d => (
          <div key={d} className="mb-[2px] grid" style={{ gridTemplateColumns: cols }}>
            <div className="pr-1 text-right text-[10px] leading-[11px] text-muted" aria-hidden="true">
              {dayLabels[d]}
            </div>
            {weeks.map((w, wi) => {
              const t = w[d]
              const count = counts.get(key(t)) ?? 0
              const future = t > today
              return (
                <div
                  key={wi}
                  data-day={future ? undefined : key(t)}
                  data-count={future ? undefined : count}
                  title={future ? undefined : `${key(t)} : ${count} action${count > 1 ? "s" : ""}`}
                  className={`size-[11px] rounded-[2px] ${future ? "bg-transparent" : LEVELS[levelOf(count)]}`}
                />
              )
            })}
          </div>
        ))}
        <figcaption className="mt-2 flex items-center gap-1 text-[10px] text-muted" aria-hidden="true">
          <span>Moins</span>
          {LEVELS.map(c => (
            <div key={c} className={`size-[11px] rounded-[2px] ${c}`} />
          ))}
          <span>Plus</span>
        </figcaption>
      </div>
    </figure>
  )
}
