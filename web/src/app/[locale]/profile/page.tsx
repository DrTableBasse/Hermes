import { headers } from 'next/headers'
import Image from 'next/image'
import { getTranslations } from 'next-intl/server'
import { redirect } from 'next/navigation'
import { auth } from '@/lib/auth'
import AchievementsPanel from '@/components/AchievementsPanel'
import { serverGetUserStats, serverGetUserAchievementsAll } from '@/lib/server-api'
import { format } from 'date-fns'
import { fr, enUS } from 'date-fns/locale'

export default async function ProfilePage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params
  const t  = await getTranslations('profile')
  const tc = await getTranslations('common')
  const dateLocale = locale === 'fr' ? fr : enUS

  const session = await auth.api.getSession({ headers: await headers() })
  type UserWithExtras = NonNullable<typeof session>['user'] & { discordId?: string }
  const u = session?.user as UserWithExtras | undefined
  if (!u?.discordId) redirect(`/${locale}`)

  const token = (session!.session as any).token as string

  let data = null
  try { data = await serverGetUserStats(u.discordId, token) } catch {}

  let allAchievements: import('@/lib/api').AchievementWithStatus[] = []
  try { allAchievements = await serverGetUserAchievementsAll(u.discordId) } catch {}

  if (!data) {
    return (
      <div className="container mx-auto px-4 py-12 text-center">
        <p className="text-muted-foreground">{tc('error')}</p>
      </div>
    )
  }

  const { user: usr, stats } = data
  const voiceH = Math.floor(stats.voice_hours)
  const voiceM = Math.round((stats.voice_hours - voiceH) * 60)

  return (
    <div className="container mx-auto px-4 py-12 max-w-3xl">
      {/* Profile header */}
      <div className="flex items-center gap-5 mb-12 glass-card p-6">
        {usr.discord_avatar ? (
          <Image src={usr.discord_avatar} alt={usr.username} width={80} height={80}
               className="w-20 h-20 rounded-full ring-4 ring-border/60" />
        ) : (
          <div className="w-20 h-20 rounded-full bg-accent flex items-center justify-center text-3xl font-bold ring-4 ring-border/60">
            {usr.username[0]?.toUpperCase()}
          </div>
        )}
        <div className="flex-1">
          <h1 className="text-3xl font-extrabold tracking-tight">{usr.nickname ?? usr.username}</h1>
          {usr.nickname && <p className="text-muted-foreground">@{usr.username}</p>}
          {usr.last_seen && (
            <p className="text-xs text-muted-foreground mt-1">
              Vu le {format(new Date(usr.last_seen), 'dd/MM/yyyy', { locale: dateLocale })}
            </p>
          )}
        </div>
      </div>

      {/* Stats */}
      <section className="mb-12">
        <h2 className="text-xl font-bold mb-5">{t('stats')}</h2>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          {[
            { label: t('messages'),    value: stats.total_messages.toLocaleString(), icon: '💬', sub: `#${stats.msg_rank}` },
            { label: t('voice_hours'), value: `${voiceH}h ${voiceM}m`,              icon: '🎤', sub: `#${stats.voice_rank}` },
            { label: t('warnings'),    value: stats.warn_count.toString(),           icon: stats.warn_count === 0 ? '✅' : '⚠️', sub: stats.warn_count === 0 ? 'Clean' : 'Actifs' },
            { label: t('bumps'),       value: (stats.bump_count ?? 0).toLocaleString(), icon: '📣', sub: `#${stats.bump_rank ?? '—'}` },
            {
              label: 'Streak vocal',
              value: stats.current_streak > 0 ? `${stats.current_streak}j` : '—',
              icon: stats.current_streak >= 14 ? '🔥🔥🔥' : stats.current_streak >= 7 ? '🔥🔥' : stats.current_streak >= 1 ? '🔥' : '❄️',
              sub: stats.current_streak >= 1 ? `×${stats.xp_multiplier?.toFixed(1) ?? '1.0'} XP · record ${stats.max_streak ?? 0}j` : 'Rejoins un vocal !',
            },
            {
              label: 'Streak messages',
              value: (stats.msg_current_streak ?? 0) > 0 ? `${stats.msg_current_streak}j` : '—',
              icon: (stats.msg_current_streak ?? 0) >= 14 ? '💬🔥🔥' : (stats.msg_current_streak ?? 0) >= 7 ? '💬🔥' : (stats.msg_current_streak ?? 0) >= 1 ? '💬' : '🔇',
              sub: (stats.msg_current_streak ?? 0) >= 1 ? `record ${stats.msg_max_streak ?? 0}j` : 'Envoie un message !',
            },
          ].map(({ label, value, icon, sub }) => (
            <div key={label} className="stat-card">
              <div className="text-3xl mb-2">{icon}</div>
              <div className="text-2xl font-extrabold tabular-nums">{value}</div>
              <div className="text-sm text-muted-foreground mt-1">{label}</div>
              <div className="text-xs text-primary font-medium mt-1.5">{sub}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Achievements */}
      <section>
        <h2 className="text-xl font-bold mb-5">{t('achievements')}</h2>
        <AchievementsPanel achievements={allAchievements} />
      </section>
    </div>
  )
}
