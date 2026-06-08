import Image from 'next/image'
import type { Metadata } from 'next'
import { serverGetUserPublicStats, serverGetUserActivity } from '@/lib/server-api'
import ActivityHeatmap from '@/components/ActivityHeatmap'
import type { ActivityDay } from '@/lib/api'

interface Props {
  params: Promise<{ locale: string; userId: string }>
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { userId } = await params
  try {
    const u = await serverGetUserPublicStats(userId)
    const name = u.nickname ?? u.username
    return {
      title: `${name} — Profil Hermes`,
      description: `Niveau ${u.stats.current_level} · ${u.stats.total_xp.toLocaleString()} XP · ${u.stats.achievement_count} achievements · ${u.stats.voice_formatted} en vocal`,
      openGraph: {
        title: `${name} sur Hermes`,
        description: `Niveau ${u.stats.current_level} · ${u.stats.total_xp.toLocaleString()} XP`,
        ...(u.discord_avatar ? { images: [{ url: u.discord_avatar, width: 128, height: 128 }] } : {}),
      },
    }
  } catch {
    return { title: 'Profil introuvable' }
  }
}

function tierLabel(points: number): { label: string; icon: string; cls: string } {
  if (points >= 100) return { label: 'Légendaire', icon: '⭐', cls: 'bg-yellow-500/20 text-yellow-300 ring-yellow-500/40' }
  if (points >= 50)  return { label: 'Épique',     icon: '💎', cls: 'bg-indigo-500/20 text-indigo-300 ring-indigo-500/40' }
  if (points >= 25)  return { label: 'Rare',       icon: '🔶', cls: 'bg-orange-500/20 text-orange-300 ring-orange-500/40' }
  return               { label: 'Commun',     icon: '⚪', cls: 'bg-neutral-500/20 text-neutral-300 ring-neutral-500/40' }
}

export default async function PublicProfilePage({ params }: Props) {
  const { userId } = await params

  let user: Awaited<ReturnType<typeof serverGetUserPublicStats>> | null = null
  let activityData: ActivityDay[] = []

  try {
    ;[user, activityData] = await Promise.all([
      serverGetUserPublicStats(userId),
      serverGetUserActivity(userId).catch(() => []),
    ])
  } catch {
    return (
      <div className="container mx-auto px-4 py-12 text-center">
        <p className="text-3xl mb-3">👤</p>
        <p className="text-muted-foreground">Membre introuvable.</p>
      </div>
    )
  }

  if (!user) return null

  const statCards = [
    { label: 'Niveau',       value: user.stats.current_level.toString(),              icon: '🏅' },
    { label: 'XP total',     value: user.stats.total_xp.toLocaleString(),             icon: '✨' },
    { label: 'Messages',     value: user.stats.total_messages.toLocaleString(),        icon: '💬' },
    { label: 'Temps vocal',  value: user.stats.voice_formatted,                       icon: '🎤' },
    { label: 'Achievements', value: user.stats.achievement_count.toString(),           icon: '🏆' },
    { label: 'Streak',       value: user.stats.current_streak > 0 ? `${user.stats.current_streak}j` : '—', icon: '🔥' },
  ]

  const tierCounts = { Légendaire: 0, Épique: 0, Rare: 0, Commun: 0 } as Record<string, number>
  for (const a of user.achievements) {
    const { label } = tierLabel(a.points)
    tierCounts[label]++
  }
  const reputationBadges = [
    { label: 'Légendaire', icon: '⭐', cls: 'bg-yellow-500/20 text-yellow-300 ring-yellow-500/40' },
    { label: 'Épique',     icon: '💎', cls: 'bg-indigo-500/20 text-indigo-300 ring-indigo-500/40' },
    { label: 'Rare',       icon: '🔶', cls: 'bg-orange-500/20 text-orange-300 ring-orange-500/40' },
    { label: 'Commun',     icon: '⚪', cls: 'bg-neutral-500/20 text-neutral-300 ring-neutral-500/40' },
  ].filter(b => (tierCounts[b.label] ?? 0) > 0)

  return (
    <div className="container mx-auto px-4 py-12 max-w-3xl">
      {/* Header */}
      <div className="flex items-center gap-5 mb-10 glass-card p-6">
        {user.discord_avatar ? (
          <Image
            src={user.discord_avatar}
            alt={user.username}
            width={80}
            height={80}
            priority
            className="w-20 h-20 rounded-full ring-4 ring-border/60"
          />
        ) : (
          <div className="w-20 h-20 rounded-full bg-accent flex items-center justify-center text-3xl font-bold ring-4 ring-border/60">
            {user.username[0]?.toUpperCase()}
          </div>
        )}
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight">{user.nickname ?? user.username}</h1>
          {user.nickname && <p className="text-muted-foreground">@{user.username}</p>}
        </div>
      </div>

      {/* Stats */}
      <section className="mb-10">
        <h2 className="text-xl font-bold mb-5">Statistiques</h2>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          {statCards.map(({ label, value, icon }) => (
            <div key={label} className="stat-card">
              <div className="text-3xl mb-2">{icon}</div>
              <div className="text-2xl font-extrabold tabular-nums">{value}</div>
              <div className="text-sm text-muted-foreground mt-1">{label}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Activité */}
      {activityData.length > 0 && (
        <section className="mb-10">
          <h2 className="text-xl font-bold mb-5">Activité (12 derniers mois)</h2>
          <div className="glass-card p-6">
            <ActivityHeatmap data={activityData} />
          </div>
        </section>
      )}

      {/* Réputation */}
      {reputationBadges.length > 0 && (
        <section className="mb-8">
          <h2 className="text-xl font-bold mb-4">Réputation</h2>
          <div className="flex flex-wrap gap-2">
            {reputationBadges.map(b => (
              <span key={b.label} className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-semibold ring-1 ${b.cls}`}>
                {b.icon} {tierCounts[b.label]} {b.label}
              </span>
            ))}
          </div>
        </section>
      )}

      {/* Achievements */}
      {user.achievements.length > 0 && (
        <section>
          <h2 className="text-xl font-bold mb-5">Achievements ({user.achievements.length})</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {user.achievements.map(a => {
              const tier = tierLabel(a.points)
              return (
                <div key={a.id} className="glass-card-hover flex items-start gap-3 p-4">
                  <span className="text-3xl">{a.icon}</span>
                  <div className="min-w-0 flex-1">
                    <p className="font-semibold">{a.name}</p>
                    <p className="text-sm text-muted-foreground">{a.description}</p>
                    <div className="flex items-center gap-2 mt-1.5">
                      <span className={`text-xs px-2 py-0.5 rounded-full ring-1 font-medium ${tier.cls}`}>
                        {tier.icon} {tier.label}
                      </span>
                      <span className="text-xs text-primary font-medium">+{a.points} pts</span>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </section>
      )}
    </div>
  )
}
