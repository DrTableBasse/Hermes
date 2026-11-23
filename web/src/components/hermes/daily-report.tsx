import type { HermesCurvePoint, HermesStatus } from "@/lib/api/types"
import { formatNumber } from "@/lib/format"

const SPARK_H = 36
const BAR_W = 4
const BAR_STEP = 6

type Bar = { x: number; y: number; height: number; last: boolean }

/** Barres du mini-graphique ; une heure sans relevé (`null`) laisse un vide, aucune valeur inventée. */
export function sparkBars(points: HermesCurvePoint[]): Bar[] {
  const values = points.map(p => p.messages).filter((v): v is number => v !== null)
  const max = Math.max(1, ...values)
  const bars: Bar[] = []
  points.forEach((p, i) => {
    if (p.messages === null) return
    const height = Math.max(1, Math.round((p.messages / max) * (SPARK_H - 4) * 10) / 10)
    bars.push({ x: i * BAR_STEP, y: SPARK_H - height, height, last: i === points.length - 1 })
  })
  return bars
}

function Sparkline({ points }: { points: HermesCurvePoint[] }) {
  const bars = sparkBars(points)
  const width = Math.max(1, points.length * BAR_STEP - (BAR_STEP - BAR_W))
  return (
    <svg
      viewBox={`0 0 ${width} ${SPARK_H}`}
      width={width}
      height={SPARK_H}
      className="max-w-full justify-self-end"
      role="img"
      aria-label="Messages heure par heure sur les dernières 24 heures"
      data-testid="hermes-spark"
    >
      {bars.map(b => (
        <rect
          key={b.x}
          x={b.x}
          y={b.y}
          width={BAR_W}
          height={b.height}
          rx="1.5"
          fill={b.last ? "#3FE0F0" : "#4D7CFF"}
          fillOpacity={b.last ? 1 : 0.45}
        />
      ))}
    </svg>
  )
}

type Row = { label: string; value: number; curve?: HermesCurvePoint[] }

/** Lignes du rapport ; une valeur `null` retire sa ligne. */
export function reportRows(status: HermesStatus): Row[] {
  const rows: Row[] = []
  const measured = status.daily_curve.filter(p => p.messages !== null)
  if (measured.length > 0) {
    rows.push({
      label: "Messages sur 24 heures",
      value: measured.reduce((sum, p) => sum + (p.messages ?? 0), 0),
      curve: status.daily_curve,
    })
  }
  const { xp_distributed, achievements, tickets, bump_reminders } = status.today
  if (xp_distributed !== null) rows.push({ label: "XP distribuée", value: xp_distributed })
  if (achievements !== null) rows.push({ label: "Succès débloqués", value: achievements })
  if (tickets !== null) rows.push({ label: "Tickets ouverts", value: tickets })
  if (bump_reminders !== null) rows.push({ label: "Rappels de bump envoyés", value: bump_reminders })
  return rows
}

/** Rapport du jour : chiffres réels depuis minuit (Paris) et courbe des messages sur 24 h. */
export function DailyReport({ status }: { status: HermesStatus | null }) {
  const rows = status ? reportRows(status) : []
  return (
    <div className="grid content-start gap-3.5 rounded-2xl border border-line bg-[rgb(12_14_26/0.6)] p-[18px]">
      <h2 className="m-0 font-display text-lg font-bold">Rapport du jour</h2>
      {rows.length > 0 ? (
        <dl className="m-0 grid gap-3.5" data-testid="hermes-report">
          {rows.map(r => (
            <div key={r.label} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3">
              <dt className="text-[13px] text-muted">{r.label}</dt>
              <dd className="col-start-1 m-0 font-display text-[22px] font-bold tabular-nums">{formatNumber(r.value)}</dd>
              {r.curve && (
                <dd className="col-start-2 row-span-2 row-start-1 m-0 grid">
                  <Sparkline points={r.curve} />
                </dd>
              )}
            </div>
          ))}
        </dl>
      ) : (
        <p className="m-0 text-sm text-muted">Rapport indisponible. Hermes rédige encore, ou se tait.</p>
      )}
    </div>
  )
}
