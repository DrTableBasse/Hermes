import { XpBar } from "@/components/ui/xp-bar"
import type { Quest } from "@/lib/api/types"
import { cn } from "@/lib/cn"
import { formatNumber } from "@/lib/format"

type WeeklyQuestsProps = {
  /** `/quests` exige une session : sans elle, invitation à se connecter. */
  signedIn: boolean
  /** `null` : API indisponible (ou pas de session). */
  quests: Quest[] | null
}

function statusText(q: Quest): string {
  if (q.status === "claimed") return "Récompense ajoutée à ton XP"
  if (q.status === "completed") return "Terminée, bien joué"
  return `${formatNumber(q.current_progress)} sur ${formatNumber(q.target_value)}`
}

function Note({ children }: { children: React.ReactNode }) {
  return <p className="m-0 text-sm text-muted">{children}</p>
}

/** Quêtes de la semaine (`/quests`), avec l'avancement du membre connecté. */
export function WeeklyQuests({ signedIn, quests }: WeeklyQuestsProps) {
  return (
    <div className="grid content-start gap-4">
      <h2 className="m-0 font-display text-lg font-bold">Quêtes de la semaine</h2>
      {!signedIn ? (
        <Note>Connecte-toi avec Discord (bouton « Connexion » en haut) pour voir les quêtes de la semaine et ton avancement.</Note>
      ) : quests === null ? (
        <Note>Quêtes indisponibles pour l’instant. Hermes recompte.</Note>
      ) : quests.length === 0 ? (
        <Note>Pas de quête cette semaine. Repos, soldat.</Note>
      ) : (
        <ul className="m-0 grid list-none gap-3 p-0">
          {quests.map(q => {
            const done = q.status !== "active"
            const ratio = q.target_value > 0 ? q.current_progress / q.target_value : done ? 1 : 0
            return (
              <li
                key={q.id}
                className={cn(
                  "grid gap-2 rounded-[14px] border bg-[rgb(12_14_26/0.55)] p-3.5",
                  done ? "border-green/40" : "border-line",
                )}
              >
                <div className="flex justify-between gap-2.5 text-sm font-semibold">
                  <span>{q.title}</span>
                  <span className={cn("font-display whitespace-nowrap", done ? "text-green" : "text-cyan")}>
                    +{formatNumber(q.xp_reward)} XP
                  </span>
                </div>
                {q.description && <small className="text-xs text-muted">{q.description}</small>}
                <XpBar
                  ratio={done ? 1 : ratio}
                  color={done ? "var(--color-green)" : undefined}
                  label={`Avancement de la quête « ${q.title} »`}
                />
                <small className="text-xs text-muted">{statusText(q)}</small>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
