'use client'

import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
  Cell,
} from 'recharts'
import type { AnalyticsData } from './actions'

const CHART_COLORS = {
  warn:    '#f59e0b',
  kick:    '#f97316',
  ban:     '#ef4444',
  timeout: '#a855f7',
  primary: '#6366f1',
  success: '#22c55e',
}

const TICK_STYLE = { fill: 'hsl(240 5% 64.9%)', fontSize: 11 }
const GRID_COLOR = 'hsl(240 3.7% 15.9%)'

function ChartCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="glass-card p-5">
      <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-4">{title}</h3>
      {children}
    </div>
  )
}

function KpiCard({ icon, value, label }: { icon: string; value: string | number; label: string }) {
  return (
    <div className="stat-card">
      <div className="text-3xl mb-2">{icon}</div>
      <div className="text-3xl font-extrabold">{typeof value === 'number' ? value.toLocaleString('fr-FR') : value}</div>
      <div className="text-sm text-muted-foreground">{label}</div>
    </div>
  )
}

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-lg border border-border bg-card px-3 py-2 text-xs shadow-xl">
      <p className="font-semibold mb-1 text-foreground">{label}</p>
      {payload.map((p: any) => (
        <p key={p.dataKey} style={{ color: p.fill ?? p.color }}>
          {p.name}: <span className="font-bold">{p.value}</span>
        </p>
      ))}
    </div>
  )
}

export function AnalyticsDashboard({ data }: { data: AnalyticsData }) {
  const hasActions = data.actions_14d.some(d => d.warn + d.kick + d.ban + d.timeout > 0)
  const hasXp      = data.top_xp_weekly.length > 0
  const hasQuests  = data.quest_completion.length > 0
  const hasLevels  = data.level_distribution.length > 0

  return (
    <div className="space-y-6">
      {/* KPI cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard icon="👥" value={data.summary.active_members}  label="Membres actifs" />
        <KpiCard icon="💬" value={data.summary.total_messages}  label="Messages au total" />
        <KpiCard icon="⚠️" value={data.summary.warns_30d}       label="Sanctions (30j)" />
        <KpiCard icon="✅" value={data.summary.quests_done_7d}  label="Quêtes complétées (7j)" />
      </div>

      {/* Charts row 1 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <ChartCard title="Sanctions — 14 derniers jours">
          {hasActions ? (
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={data.actions_14d} margin={{ top: 0, right: 0, bottom: 0, left: -20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={GRID_COLOR} vertical={false} />
                <XAxis dataKey="label" tick={TICK_STYLE} axisLine={false} tickLine={false} />
                <YAxis tick={TICK_STYLE} axisLine={false} tickLine={false} allowDecimals={false} />
                <Tooltip content={<CustomTooltip />} cursor={{ fill: 'hsl(240 3.7% 15.9%)' }} />
                <Legend wrapperStyle={{ fontSize: 11, color: 'hsl(240 5% 64.9%)' }} />
                <Bar dataKey="warn"    name="Warn"    fill={CHART_COLORS.warn}    radius={[2, 2, 0, 0]} stackId="a" />
                <Bar dataKey="timeout" name="Mute"    fill={CHART_COLORS.timeout} radius={[2, 2, 0, 0]} stackId="a" />
                <Bar dataKey="kick"    name="Kick"    fill={CHART_COLORS.kick}    radius={[2, 2, 0, 0]} stackId="a" />
                <Bar dataKey="ban"     name="Ban"     fill={CHART_COLORS.ban}     radius={[2, 2, 0, 0]} stackId="a" />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-60 text-muted-foreground text-sm">
              Aucune sanction sur les 14 derniers jours
            </div>
          )}
        </ChartCard>

        <ChartCard title="Distribution des niveaux">
          {hasLevels ? (
            <ResponsiveContainer width="100%" height={240}>
              <BarChart
                data={data.level_distribution}
                layout="vertical"
                margin={{ top: 0, right: 16, bottom: 0, left: 8 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke={GRID_COLOR} horizontal={false} />
                <XAxis type="number" tick={TICK_STYLE} axisLine={false} tickLine={false} allowDecimals={false} />
                <YAxis type="category" dataKey="level_range" tick={TICK_STYLE} axisLine={false} tickLine={false} width={36} />
                <Tooltip content={<CustomTooltip />} cursor={{ fill: 'hsl(240 3.7% 15.9%)' }} />
                <Bar dataKey="count" name="Membres" radius={[0, 4, 4, 0]}>
                  {data.level_distribution.map((_, i) => (
                    <Cell key={i} fill={`hsl(${235 + i * 15} 86% ${55 + i * 5}%)`} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-60 text-muted-foreground text-sm">
              Aucune donnée XP
            </div>
          )}
        </ChartCard>
      </div>

      {/* Charts row 2 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <ChartCard title="Complétion des quêtes — semaine en cours">
          {hasQuests ? (
            <ResponsiveContainer width="100%" height={240}>
              <BarChart
                data={data.quest_completion}
                layout="vertical"
                margin={{ top: 0, right: 16, bottom: 0, left: 8 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke={GRID_COLOR} horizontal={false} />
                <XAxis type="number" tick={TICK_STYLE} axisLine={false} tickLine={false} domain={[0, 100]} unit="%" />
                <YAxis
                  type="category"
                  dataKey="title"
                  tick={TICK_STYLE}
                  axisLine={false}
                  tickLine={false}
                  width={140}
                  tickFormatter={v => v.length > 18 ? v.slice(0, 18) + '…' : v}
                />
                <Tooltip
                  content={({ active, payload, label }) => {
                    if (!active || !payload?.length) return null
                    const d = payload[0].payload
                    return (
                      <div className="rounded-lg border border-border bg-card px-3 py-2 text-xs shadow-xl">
                        <p className="font-semibold mb-1 text-foreground">{label}</p>
                        <p style={{ color: CHART_COLORS.success }}>{d.completed}/{d.participants} complétés ({d.rate}%)</p>
                      </div>
                    )
                  }}
                  cursor={{ fill: 'hsl(240 3.7% 15.9%)' }}
                />
                <Bar dataKey="rate" name="Taux %" fill={CHART_COLORS.success} radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-60 text-muted-foreground text-sm">
              Aucune quête active cette semaine
            </div>
          )}
        </ChartCard>

        <ChartCard title="Top 5 XP — semaine en cours">
          {hasXp ? (
            <ResponsiveContainer width="100%" height={240}>
              <BarChart
                data={data.top_xp_weekly}
                layout="vertical"
                margin={{ top: 0, right: 16, bottom: 0, left: 8 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke={GRID_COLOR} horizontal={false} />
                <XAxis type="number" tick={TICK_STYLE} axisLine={false} tickLine={false} allowDecimals={false} />
                <YAxis
                  type="category"
                  dataKey="username"
                  tick={TICK_STYLE}
                  axisLine={false}
                  tickLine={false}
                  width={80}
                  tickFormatter={v => v.length > 12 ? v.slice(0, 12) + '…' : v}
                />
                <Tooltip content={<CustomTooltip />} cursor={{ fill: 'hsl(240 3.7% 15.9%)' }} />
                <Bar dataKey="weekly_xp" name="XP" radius={[0, 4, 4, 0]}>
                  {data.top_xp_weekly.map((_, i) => {
                    const colors = ['#f59e0b', '#94a3b8', '#c07a3b', CHART_COLORS.primary, CHART_COLORS.primary]
                    return <Cell key={i} fill={colors[i] ?? CHART_COLORS.primary} />
                  })}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-60 text-muted-foreground text-sm">
              Aucun XP gagné cette semaine
            </div>
          )}
        </ChartCard>
      </div>
    </div>
  )
}
