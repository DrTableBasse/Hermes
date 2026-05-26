export default function StreakBadge({ streak }: { streak: number }) {
  if (streak === 0) return null
  const emoji = streak >= 30 ? '🔥🔥🔥' : streak >= 14 ? '🔥🔥' : '🔥'
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-orange-500/20 text-orange-400 text-xs font-medium">
      {emoji} {streak}j
    </span>
  )
}
