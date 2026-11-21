import type { CSSProperties, ReactNode } from "react"
import { Panel } from "@/components/ui/panel"
import type { AnalyticsData } from "@/lib/api/types"
import { formatNumber } from "@/lib/format"

const SANCTIONS = [
  { key: "warn", label: "Avertissements", color: "var(--color-gold)" },
  { key: "timeout", label: "Exclusions temporaires", color: "var(--color-violet)" },
  { key: "kick", label: "Expulsions", color: "var(--color-orange)" },
  { key: "ban", label: "Bannissements", color: "#FF5A5A" },
] as const

function Card({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Panel as="section" className="grid content-start gap-4">
      <h2 className="m-0 font-display text-lg font-bold">{title}</h2>
      {children}
    </Panel>
  )
}

/** Barres horizontales : libellé, barre proportionnelle, valeur lue en texte (pas de couleur seule). */
function Bars({ rows, unit = "" }: { rows: Array<{ label: string; value: number; text?: string }>; unit?: string }) {
  const max = Math.max(1, ...rows.map(r => r.value))
  return (
    <ul className="m-0 grid list-none gap-2.5 p-0">
      {rows.map(r => (
        <li key={r.label} className="grid grid-cols-[minmax(0,9rem)_1fr_auto] items-center gap-3 text-sm">
          <span className="truncate text-msg" title={r.label}>
            {r.label}
          </span>
          <span className="h-2.5 overflow-hidden rounded-full bg-white/6" aria-hidden="true">
            <span className="block h-full rounded-full bg-violet" style={{ width: `${(r.value / max) * 100}%` }} />
          </span>
          <span className="tabular-nums text-muted">{r.text ?? `${formatNumber(r.value)}${unit}`}</span>
        </li>
      ))}
    </ul>
  )
}

/** Tableau de bord : indicateurs, sanctions sur 14 jours, niveaux, quêtes, top XP de la semaine. */
export function AnalyticsDashboard({ data }: { data: AnalyticsData }) {
  const days = data.actions_14d
  const dayTotal = (d: (typeof days)[number]) => d.warn + d.kick + d.ban + d.timeout
  const maxDay = Math.max(1, ...days.map(dayTotal))
  const hasActions = days.some(d => dayTotal(d) > 0)

  return (
    <div className="grid gap-6">
      <dl className="m-0 grid grid-cols-2 gap-4 lg:grid-cols-4">
        {[
          ["Membres", data.summary.active_members],
          ["Messages au total", data.summary.total_messages],
          ["Sanctions (30 j)", data.summary.warns_30d],
          ["Quêtes terminées (7 j)", data.summary.quests_done_7d],
        ].map(([label, value]) => (
          <Panel key={label} className="grid gap-1 p-5">
            <dt className="text-sm text-muted">{label}</dt>
            <dd className="m-0 font-display text-3xl font-extrabold tabular-nums">{formatNumber(Number(value))}</dd>
          </Panel>
        ))}
      </dl>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Sanctions — 14 derniers jours">
          {hasActions ? (
            <>
              <ol className="m-0 flex h-44 list-none items-end gap-1.5 p-0" aria-label="Sanctions par jour">
                {days.map(d => (
                  <li key={d.date} className="flex h-full flex-1 flex-col justify-end" aria-label={`${d.label} : ${dayTotal(d)} sanction(s)`}>
                    <span className="flex flex-col-reverse overflow-hidden rounded-t-md" style={{ height: `${(dayTotal(d) / maxDay) * 100}%` }}>
                      {SANCTIONS.map(s =>
                        d[s.key] > 0 ? (
                          <span key={s.key} style={{ flexGrow: d[s.key], background: s.color } as CSSProperties} className="block min-h-1" />
                        ) : null,
                      )}
                    </span>
                    <span className="mt-1 text-center text-[10px] text-muted" aria-hidden="true">
                      {d.label.slice(3)}
                    </span>
                  </li>
                ))}
              </ol>
              <ul className="m-0 flex list-none flex-wrap gap-x-4 gap-y-1 p-0 text-xs text-muted">
                {SANCTIONS.map(s => (
                  <li key={s.key} className="inline-flex items-center gap-1.5">
                    <i className="size-2.5 rounded-sm" style={{ background: s.color }} aria-hidden="true" />
                    {s.label} ({days.reduce((n, d) => n + d[s.key], 0)})
                  </li>
                ))}
              </ul>
            </>
          ) : (
            <p className="m-0 text-sm text-muted">Aucune sanction sur les 14 derniers jours.</p>
          )}
        </Card>

        <Card title="Répartition des niveaux">
          {data.level_distribution.length ? (
            <Bars rows={data.level_distribution.map(l => ({ label: `Niveaux ${l.level_range}`, value: l.count }))} />
          ) : (
            <p className="m-0 text-sm text-muted">Aucune donnée d’XP.</p>
          )}
        </Card>

        <Card title="Quêtes de la semaine — taux de réussite">
          {data.quest_completion.length ? (
            <Bars
              rows={data.quest_completion.map(q => ({
                label: q.title,
                value: q.rate,
                text: `${q.completed}/${q.participants} (${q.rate} %)`,
              }))}
            />
          ) : (
            <p className="m-0 text-sm text-muted">Aucune quête active cette semaine.</p>
          )}
        </Card>

        <Card title="Top 5 XP — semaine en cours">
          {data.top_xp_weekly.length ? (
            <Bars rows={data.top_xp_weekly.map(u => ({ label: u.username, value: u.weekly_xp }))} unit=" XP" />
          ) : (
            <p className="m-0 text-sm text-muted">Aucun XP gagné cette semaine.</p>
          )}
        </Card>
      </div>
    </div>
  )
}
