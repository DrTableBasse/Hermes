import { Quest } from '@/lib/api'

interface Props {
  quest: Quest
  onClaim?: (id: number) => void
}

export default function QuestCard({ quest, onClaim }: Props) {
  const progress = Math.min(100, Math.round((quest.current_progress / quest.target_value) * 100))
  const isCompleted = quest.status === 'completed'
  const isClaimed = quest.status === 'claimed'

  return (
    <div className={`glass-card p-5 transition-all ${
      isClaimed ? 'border-success/30 bg-success/5' : ''
    }`}>
      <div className="flex items-start justify-between mb-3">
        <div>
          <h4 className="font-semibold text-sm">{quest.title}</h4>
          <p className="text-xs text-muted-foreground mt-0.5">{quest.description}</p>
        </div>
        <span className="text-gold text-xs font-bold whitespace-nowrap ml-3">+{quest.xp_reward} XP</span>
      </div>
      <div className="mt-3">
        <div className="flex justify-between text-xs text-muted-foreground mb-1.5">
          <span>{quest.current_progress} / {quest.target_value}</span>
          <span>{progress}%</span>
        </div>
        <div className="h-2 bg-secondary rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${
              isClaimed ? 'bg-success' : 'bg-primary'
            }`}
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>
      {isCompleted && !isClaimed && onClaim && (
        <button
          onClick={() => onClaim(quest.id)}
          className="mt-4 w-full py-2 text-xs font-semibold bg-gold hover:opacity-90 text-primary-foreground rounded-lg transition-all"
        >
          Réclamer la récompense
        </button>
      )}
      {isClaimed && (
        <p className="mt-3 text-xs text-success text-center font-medium">✓ Récompense réclamée</p>
      )}
    </div>
  )
}
