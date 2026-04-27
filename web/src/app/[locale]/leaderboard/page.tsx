import { getTranslations } from 'next-intl/server'
import { api } from '@/lib/api'

export default async function LeaderboardPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params
  const t = await getTranslations('leaderboard')

  let msgLb:   any[] = []
  let voiceLb: any[] = []
  try {
    msgLb   = (await api.leaderboard.messages(20)).leaderboard
    voiceLb = (await api.leaderboard.voice(20)).leaderboard
  } catch {}

  const medal = (i: number) => i === 0 ? '🥇' : i === 1 ? '🥈' : i === 2 ? '🥉' : `${i + 1}.`

  const Avatar = ({ src, name }: { src: string | null; name: string }) =>
    src ? (
      <img src={src} alt={name} className="w-9 h-9 rounded-full" />
    ) : (
      <div className="w-9 h-9 rounded-full bg-accent flex items-center justify-center font-bold text-sm">
        {name[0]?.toUpperCase()}
      </div>
    )

  return (
    <div className="container mx-auto px-4 py-12 max-w-4xl">
      <h1 className="text-3xl font-bold mb-10">{t('title')}</h1>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        {/* Messages */}
        <section>
          <h2 className="text-xl font-semibold mb-4">💬 {t('messages_tab')}</h2>
          <div className="space-y-2">
            {msgLb.map((e, i) => (
              <div key={e.user_id} className="flex items-center gap-3 p-3 rounded-lg border border-border bg-card">
                <span className="w-8 text-center font-bold">{medal(i)}</span>
                <Avatar src={e.discord_avatar} name={e.username} />
                <span className="flex-1 font-medium truncate">{e.username}</span>
                <span className="text-sm text-muted-foreground tabular-nums">
                  {e.total_messages.toLocaleString()}
                </span>
              </div>
            ))}
          </div>
        </section>

        {/* Voice */}
        <section>
          <h2 className="text-xl font-semibold mb-4">🎤 {t('voice_tab')}</h2>
          <div className="space-y-2">
            {voiceLb.map((e, i) => (
              <div key={e.user_id} className="flex items-center gap-3 p-3 rounded-lg border border-border bg-card">
                <span className="w-8 text-center font-bold">{medal(i)}</span>
                <Avatar src={e.discord_avatar} name={e.username} />
                <span className="flex-1 font-medium truncate">{e.username}</span>
                <span className="text-sm text-muted-foreground tabular-nums">{e.formatted}</span>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  )
}
