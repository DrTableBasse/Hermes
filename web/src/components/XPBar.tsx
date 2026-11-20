'use client'
import { XPData } from '@/lib/api'

// Même formule que le bot (bot/utils/database.py, XPManager.xp_for_level) :
// le niveau N est atteint à N² × 100 XP.
function xpForLevel(level: number): number {
  return level * level * 100
}

export default function XPBar({ data }: { data: XPData }) {
  const floorXP = data.current_level <= 1 ? 0 : xpForLevel(data.current_level)
  const nextXP = xpForLevel(data.current_level + 1)
  const span = nextXP - floorXP
  const progress = span > 0
    ? Math.min(100, Math.max(0, Math.round(((data.total_xp - floorXP) / span) * 100)))
    : 100

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
