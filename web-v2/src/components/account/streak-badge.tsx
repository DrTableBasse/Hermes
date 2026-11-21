import { Flame } from "lucide-react"
import { Chip } from "@/components/ui/chip"

/** Série en jours ; une flamme de plus à 14 jours, une autre à 30. Rien à 0. */
export function StreakBadge({ streak }: { streak: number }) {
  if (!(streak > 0)) return null
  const flames = streak >= 30 ? 3 : streak >= 14 ? 2 : 1
  return (
    <Chip color="#FF8A3D" aria-label={`Série de ${streak} jour${streak > 1 ? "s" : ""}`}>
      {Array.from({ length: flames }, (_, i) => (
        <Flame key={i} className="-mr-1 size-3.5 last:mr-0" aria-hidden="true" />
      ))}
      {streak} j
    </Chip>
  )
}
