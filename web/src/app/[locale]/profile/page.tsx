import { getTranslations } from 'next-intl/server'
import { redirect } from 'next/navigation'
import { api } from '@/lib/api'
import { format } from 'date-fns'
import { fr, enUS } from 'date-fns/locale'

export default async function ProfilePage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params
  const t  = await getTranslations('profile')
  const tc = await getTranslations('common')
  const dateLocale = locale === 'fr' ? fr : enUS

  let user = null
  try { user = await api.auth.me() } catch {}
  if (!user) redirect(`/${locale}`)

  let data = null
  try { data = await api.users.stats(user.user_id) } catch {}

  if (!data) {
    return (
      <div className="container mx-auto px-4 py-12 text-center">
        <p className="text-muted-foreground">{tc('error')}</p>
      </div>
    )
  }

  const { user: u, stats, achievements } = data
  const voiceH = Math.floor(stats.voice_hours)
  const voiceM = Math.round((stats.voice_hours - voiceH) * 60)

  return (
    <div className="container mx-auto px-4 py-12 max-w-3xl">
      {/* Header */}
      <div className="flex items-center gap-5 mb-10">
        {u.discord_avatar ? (
          <img src={u.discord_avatar} alt={u.username} className="w-20 h-20 rounded-full border-2 border-border" />
        ) : (
          <div className="w-20 h-20 rounded-full bg-accent flex items-center justify-center text-3xl font-bold">
            {u.username[0]?.toUpperCase()}
          </div>
        )}
        <div>
          <h1 className="text-3xl font-bold">{u.nickname ?? u.username}</h1>
          {u.nickname && <p className="text-muted-foreground">@{u.username}</p>}
          {u.last_seen && (
            <p className="text-xs text-muted-foreground mt-1">
              Vu le {format(new Date(u.last_seen), 'dd/MM/yyyy', { locale: dateLocale })}
            </p>
          )}
        </div>
      </div>

      {/* Stats grid */}
      <section className="mb-10">
        <h2 className="text-xl font-semibold mb-4">{t('stats')}</h2>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          {[
            { label: t('messages'),   value: stats.total_messages.toLocaleString(), icon: '💬', sub: `#${stats.msg_rank}` },
            { label: t('voice_hours'),value: `${voiceH}h ${voiceM}m`,              icon: '🎤', sub: `#${stats.voice_rank}` },
            { label: t('warnings'),   value: stats.warn_count.toString(),           icon: '⚠️', sub: stats.warn_count === 0 ? '✅' : '⚠️' },
          ].map(({ label, value, icon, sub }) => (
            <div key={label} className="border border-border rounded-xl p-4 bg-card">
              <div className="text-3xl mb-1">{icon}</div>
              <div className="text-2xl font-bold">{value}</div>
              <div className="text-sm text-muted-foreground">{label}</div>
              <div className="text-xs text-primary mt-1">{sub}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Achievements */}
      <section>
        <h2 className="text-xl font-semibold mb-4">{t('achievements')}</h2>
        {achievements.length === 0 ? (
          <p className="text-muted-foreground">{t('no_achievements')}</p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {achievements.map(a => (
              <div key={a.id} className="flex items-start gap-3 border border-border rounded-xl p-4 bg-card">
                <span className="text-3xl">{a.icon}</span>
                <div>
                  <p className="font-semibold">{a.name}</p>
                  <p className="text-sm text-muted-foreground">{a.description}</p>
                  <p className="text-xs text-primary mt-1">+{a.points} pts · {t('unlocked_at')} {format(new Date(a.unlocked_at), 'dd/MM/yyyy', { locale: dateLocale })}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
