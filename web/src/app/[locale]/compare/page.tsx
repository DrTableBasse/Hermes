import Image from 'next/image'
import { serverGetUserPublicStats, type PublicUserStats } from '@/lib/server-api'
import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Comparer des membres',
}

interface Props {
  params: Promise<{ locale: string }>
  searchParams: Promise<{ u1?: string; u2?: string }>
}

function StatRow({
  label,
  v1,
  v2,
}: {
  label: string
  v1: number | string
  v2: number | string
}) {
  const n1 = typeof v1 === 'number' ? v1 : null
  const n2 = typeof v2 === 'number' ? v2 : null
  const win1 = n1 !== null && n2 !== null && n1 > n2
  const win2 = n1 !== null && n2 !== null && n2 > n1
  return (
    <tr className="border-b border-white/5">
      <td
        className={`py-2 px-3 text-right font-semibold tabular-nums ${win1 ? 'text-green-400' : 'text-foreground'}`}
      >
        {typeof v1 === 'number' ? v1.toLocaleString() : v1}
      </td>
      <td className="py-2 px-3 text-center text-xs text-muted-foreground whitespace-nowrap">
        {label}
      </td>
      <td
        className={`py-2 px-3 text-left font-semibold tabular-nums ${win2 ? 'text-green-400' : 'text-foreground'}`}
      >
        {typeof v2 === 'number' ? v2.toLocaleString() : v2}
      </td>
    </tr>
  )
}

function UserHeader({ user }: { user: PublicUserStats }) {
  return (
    <div className="flex flex-col items-center gap-2 p-4">
      {user.discord_avatar ? (
        <Image
          src={user.discord_avatar}
          alt={user.username}
          width={64}
          height={64}
          className="rounded-full ring-2 ring-border/60"
        />
      ) : (
        <div className="w-16 h-16 rounded-full bg-accent flex items-center justify-center text-2xl font-bold ring-2 ring-border/60">
          {user.username[0]?.toUpperCase()}
        </div>
      )}
      <div className="text-center">
        <p className="font-bold">{user.nickname ?? user.username}</p>
        {user.nickname && (
          <p className="text-xs text-muted-foreground">@{user.username}</p>
        )}
      </div>
    </div>
  )
}

export default async function ComparePage({ params, searchParams }: Props) {
  const { locale } = await params
  const { u1, u2 } = await searchParams

  if (!u1 || !u2) {
    return (
      <div className="container mx-auto px-4 py-12 max-w-2xl">
        <h1 className="text-3xl font-extrabold mb-6">Comparer des membres</h1>
        <div className="glass-card p-8 text-center">
          <p className="text-muted-foreground mb-4">
            Passe les IDs Discord de deux membres en paramètres URL :
          </p>
          <code className="text-sm bg-white/5 px-3 py-2 rounded block">
            /compare?u1=&#x3C;userId1&#x3E;&amp;u2=&#x3C;userId2&#x3E;
          </code>
        </div>
      </div>
    )
  }

  const [r1, r2] = await Promise.allSettled([
    serverGetUserPublicStats(u1),
    serverGetUserPublicStats(u2),
  ])

  const user1 = r1.status === 'fulfilled' ? r1.value : null
  const user2 = r2.status === 'fulfilled' ? r2.value : null

  if (!user1 || !user2) {
    return (
      <div className="container mx-auto px-4 py-12 max-w-2xl">
        <h1 className="text-3xl font-extrabold mb-6">Comparer des membres</h1>
        <div className="glass-card p-8 text-center">
          <p className="text-muted-foreground">
            {!user1 && !user2
              ? 'Aucun des deux membres trouvé.'
              : !user1
                ? `Membre ${u1} introuvable.`
                : `Membre ${u2} introuvable.`}
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="container mx-auto px-4 py-12 max-w-3xl">
      <h1 className="text-3xl font-extrabold mb-8 text-center">Comparaison</h1>

      <div className="glass-card overflow-hidden">
        {/* User headers */}
        <div className="grid grid-cols-3 border-b border-white/10">
          <UserHeader user={user1} />
          <div className="flex items-center justify-center text-2xl font-black text-muted-foreground">
            VS
          </div>
          <UserHeader user={user2} />
        </div>

        {/* Stats table */}
        <table className="w-full">
          <tbody>
            <StatRow label="Niveau"         v1={user1.stats.current_level}     v2={user2.stats.current_level} />
            <StatRow label="XP total"       v1={user1.stats.total_xp}          v2={user2.stats.total_xp} />
            <StatRow label="Messages"       v1={user1.stats.total_messages}    v2={user2.stats.total_messages} />
            <StatRow label="Temps vocal"    v1={user1.stats.voice_formatted}   v2={user2.stats.voice_formatted} />
            <StatRow label="Achievements"   v1={user1.stats.achievement_count} v2={user2.stats.achievement_count} />
            <StatRow label="Streak actuel"  v1={user1.stats.current_streak}    v2={user2.stats.current_streak} />
            <StatRow label="Bumps"          v1={user1.stats.bump_count}        v2={user2.stats.bump_count} />
          </tbody>
        </table>
      </div>
    </div>
  )
}
