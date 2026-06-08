import Image from 'next/image'
import { serverLeaderboardXpWeekly } from '@/lib/server-api'
import type { XPEntry } from '@/lib/api'
import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Top de la semaine',
}

function medalEmoji(rank: number): string {
  if (rank === 1) return '🥇'
  if (rank === 2) return '🥈'
  if (rank === 3) return '🥉'
  return `#${rank}`
}

export default async function TopWeeklyPage({
  params,
}: {
  params: Promise<{ locale: string }>
}) {
  await params

  let entries: XPEntry[] = []
  try {
    const result = await serverLeaderboardXpWeekly(20)
    entries = result.leaderboard
  } catch {}

  return (
    <div className="container mx-auto px-4 py-12 max-w-2xl">
      <h1 className="text-3xl font-extrabold mb-2">Top de la semaine</h1>
      <p className="text-muted-foreground mb-8">
        Classement par XP gagné cette semaine.
      </p>

      {entries.length === 0 ? (
        <div className="glass-card p-8 text-center">
          <p className="text-muted-foreground">Aucune activité cette semaine.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {entries.map((entry, idx) => {
            const rank = idx + 1
            return (
              <div
                key={entry.user_id}
                className={`glass-card flex items-center gap-4 px-5 py-4 ${
                  rank <= 3 ? 'ring-1 ring-primary/30' : ''
                }`}
              >
                <div className="w-9 text-center font-bold text-lg shrink-0">
                  {medalEmoji(rank)}
                </div>

                {entry.discord_avatar ? (
                  <Image
                    src={entry.discord_avatar}
                    alt={entry.username}
                    width={40}
                    height={40}
                    className="rounded-full shrink-0"
                  />
                ) : (
                  <div className="w-10 h-10 rounded-full bg-accent flex items-center justify-center font-bold shrink-0">
                    {entry.username[0]?.toUpperCase()}
                  </div>
                )}

                <div className="flex-1 min-w-0">
                  <p className="font-semibold truncate">{entry.username}</p>
                  <p className="text-xs text-muted-foreground">
                    Niveau {entry.current_level}
                  </p>
                </div>

                <div className="text-right shrink-0">
                  <p className="font-bold text-primary tabular-nums">
                    +{entry.weekly_xp.toLocaleString()} XP
                  </p>
                  <p className="text-xs text-muted-foreground tabular-nums">
                    {entry.total_xp.toLocaleString()} total
                  </p>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
