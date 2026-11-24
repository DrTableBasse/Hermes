import { XpBar } from "@/components/ui/xp-bar"
import type { Quest } from "@/lib/api/types"
import { cn } from "@/lib/cn"
import { formatNumber } from "@/lib/format"

/** Quête de la semaine. La récompense est versée automatiquement par Hermes dès qu'elle est terminée. */
export function QuestCard({ quest }: { quest: Quest }) {
  const claimed = quest.status === "claimed"
  const done = quest.status !== "active"
  const ratio = done ? 1 : quest.target_value > 0 ? quest.current_progress / quest.target_value : 0
  const percent = Math.min(100, Math.round(ratio * 100))

  return (
    <li className={cn("grid gap-3 rounded-[20px] border bg-[rgb(19_22_42/0.92)] p-5", done ? "border-green/40" : "border-line")}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="m-0 text-sm font-semibold">{quest.title}</h3>
          {quest.description && <p className="m-0 mt-0.5 text-xs text-muted">{quest.description}</p>}
        </div>
        <span className={cn("font-display text-sm font-bold whitespace-nowrap", done ? "text-green" : "text-cyan")}>
          +{formatNumber(quest.xp_reward)} XP
        </span>
      </div>
      <div>
        <div className="mb-1.5 flex justify-between text-xs text-muted tabular-nums">
          <span>
            {formatNumber(quest.current_progress)} sur {formatNumber(quest.target_value)}
          </span>
          <span>{percent} %</span>
        </div>
        <XpBar
          ratio={ratio}
          color={done ? "var(--color-green)" : undefined}
          label={`Avancement de la quête « ${quest.title} »`}
        />
      </div>
      {done && (
        <p className="m-0 text-center text-xs font-semibold text-green">
          {claimed ? "Récompense ajoutée à ton XP" : "Terminé : Hermes ajoute la récompense à ton XP"}
        </p>
      )}
    </li>
  )
}
