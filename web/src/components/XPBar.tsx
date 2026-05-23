'use client'
import { XPData } from '@/lib/api'

function xpForLevel(level: number): number {
  return Math.floor(100 * Math.pow(1.15, level - 1))
}

export default function XPBar({ data }: { data: XPData }) {
  const nextXP = xpForLevel(data.current_level + 1)
  const progress = nextXP > 0 ? Math.min(100, Math.round((data.total_xp / nextXP) * 100)) : 100

  return (
    <div className="flex items-center gap-3 text-sm">
      <span className="text-gold font-bold">Niv. {data.current_level}</span>
      <div className="flex-1">
        <div className="h-2 bg-secondary rounded-full overflow-hidden">
          <div
            className="h-full bg-gold rounded-full transition-all duration-500"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>
      <span className="text-muted-foreground text-xs tabular-nums">{data.total_xp.toLocaleString()} XP</span>
    </div>
  )
}
