import type { ActivityDay } from '@/lib/api'

interface Props {
  data: ActivityDay[]
}

function getColor(count: number): string {
  if (count === 0) return 'bg-neutral-800'
  if (count < 3)  return 'bg-green-900'
  if (count < 7)  return 'bg-green-700'
  if (count < 15) return 'bg-green-500'
  return 'bg-green-400'
}

function formatDateKey(date: Date): string {
  return date.toISOString().slice(0, 10)
}

export default function ActivityHeatmap({ data }: Props) {
  const countMap = new Map(data.map(d => [d.date, d.count]))

  // Build 52-week grid ending today
  const today = new Date()
  today.setHours(0, 0, 0, 0)

  // Find the Sunday that starts the first week (52 weeks ago)
  const start = new Date(today)
  start.setDate(today.getDate() - 7 * 52 + 1)
  // Align to Sunday
  start.setDate(start.getDate() - start.getDay())

  // Build columns (weeks), each column has 7 days (Sun–Sat)
  const weeks: Date[][] = []
  const cur = new Date(start)
  while (cur <= today) {
    const week: Date[] = []
    for (let d = 0; d < 7; d++) {
      week.push(new Date(cur))
      cur.setDate(cur.getDate() + 1)
    }
    weeks.push(week)
  }

  // Month labels: find first week where month changes
  const monthLabels: { label: string; col: number }[] = []
  let prevMonth = -1
  weeks.forEach((week, i) => {
    const m = week[0].getMonth()
    if (m !== prevMonth) {
      monthLabels.push({
        label: week[0].toLocaleString('fr-FR', { month: 'short' }),
        col: i + 1,
      })
      prevMonth = m
    }
  })

  const dayLabels = ['', 'Lun', '', 'Mer', '', 'Ven', '']

  return (
    <div className="overflow-x-auto">
      <div className="inline-block min-w-max">
        {/* Month labels */}
        <div
          className="grid mb-1"
          style={{ gridTemplateColumns: `28px repeat(${weeks.length}, 13px)` }}
        >
          <div />
          {weeks.map((_, i) => {
            const ml = monthLabels.find(m => m.col === i + 1)
            return (
              <div key={i} className="text-[10px] text-neutral-500">
                {ml?.label ?? ''}
              </div>
            )
          })}
        </div>

        {/* Grid rows (days 0–6 = Sun–Sat) */}
        {[0, 1, 2, 3, 4, 5, 6].map(dayIdx => (
          <div
            key={dayIdx}
            className="grid mb-[2px]"
            style={{ gridTemplateColumns: `28px repeat(${weeks.length}, 13px)` }}
          >
            {/* Day label */}
            <div className="text-[10px] text-neutral-500 leading-[11px] pr-1 text-right">
              {dayLabels[dayIdx]}
            </div>
            {weeks.map((week, wi) => {
              const day = week[dayIdx]
              const key = formatDateKey(day)
              const count = countMap.get(key) ?? 0
              const isFuture = day > today
              return (
                <div
                  key={wi}
                  title={`${key}: ${count} action${count !== 1 ? 's' : ''}`}
                  className={`w-[11px] h-[11px] rounded-[2px] ${
                    isFuture ? 'bg-neutral-900' : getColor(count)
                  }`}
                />
              )
            })}
          </div>
        ))}

        {/* Legend */}
        <div className="flex items-center gap-1 mt-2 text-[10px] text-neutral-500">
          <span>Moins</span>
          {['bg-neutral-800', 'bg-green-900', 'bg-green-700', 'bg-green-500', 'bg-green-400'].map(
            (c, i) => (
              <div key={i} className={`w-[11px] h-[11px] rounded-[2px] ${c}`} />
            )
          )}
          <span>Plus</span>
        </div>
      </div>
    </div>
  )
}
