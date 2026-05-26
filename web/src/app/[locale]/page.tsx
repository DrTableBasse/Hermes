import { getTranslations } from 'next-intl/server'
import Link from 'next/link'
import { headers } from 'next/headers'
import type { Article } from '@/lib/api'
import { serverListArticles, serverLeaderboardGlobal, type GlobalEntry } from '@/lib/server-api'
import { ArticleCard } from '@/components/ArticleCard'
import { LoginButton } from '@/components/LoginButton'
import { auth } from '@/lib/auth'

export default async function HomePage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params
  const t  = await getTranslations('home')
  const ta = await getTranslations('articles')

  const session    = await auth.api.getSession({ headers: await headers() }).catch(() => null)
  const isLoggedIn = !!session

  const [articles, globalTop] = await Promise.all([
    serverListArticles({ page: 1, limit: 3 }).then(r => r.articles).catch((): Article[] => []),
    serverLeaderboardGlobal(5).catch((): GlobalEntry[] => []),
  ])

  const medals = ['🥇', '🥈', '🥉']

  return (
    <div className="container mx-auto px-4 py-16">
      {/* Hero */}
      <section className="text-center mb-24 relative">
        <div className="absolute inset-0 -z-10 overflow-hidden">
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[400px] bg-primary/5 rounded-full blur-[120px]" />
        </div>
        <h1 className="text-5xl sm:text-6xl font-extrabold mb-6 gradient-hero glow-text animate-fade-up tracking-tight">
          {t('hero_title')}
        </h1>
        <p className="text-lg text-muted-foreground mb-10 max-w-2xl mx-auto animate-fade-up" style={{ animationDelay: '0.1s' }}>
          {t('hero_subtitle')}
        </p>
        {!isLoggedIn && (
          <div className="animate-fade-up" style={{ animationDelay: '0.2s' }}>
            <LoginButton
              callbackURL={`/${locale}`}
              label={t('login_with_discord')}
              className="inline-flex items-center gap-2.5 bg-discord text-white font-semibold px-8 py-3.5 rounded-xl hover:opacity-90 transition-all text-lg shadow-lg shadow-discord/20 hover:shadow-xl hover:shadow-discord/30"
            />
          </div>
        )}
      </section>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-12">
        {/* Latest articles */}
        <section className="lg:col-span-2">
          <div className="flex items-center justify-between mb-8">
            <h2 className="text-2xl font-bold">{t('latest_articles')}</h2>
            <Link href={`/${locale}/articles`} className="text-sm text-muted-foreground hover:text-foreground transition-colors">
              {t('view_all')} →
            </Link>
          </div>
          {articles.length === 0 ? (
            <p className="text-muted-foreground">{ta('no_articles')}</p>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
              {articles.map(a => (
                <ArticleCard key={a.id} article={a} locale={locale} />
              ))}
            </div>
          )}
        </section>

        {/* Global top members */}
        <section>
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-2xl font-bold">{t('top_members')}</h2>
            <Link href={`/${locale}/leaderboard`} className="text-xs text-muted-foreground hover:text-foreground transition-colors">
              Voir tout →
            </Link>
          </div>
          <div className="space-y-2">
            {globalTop.length === 0 ? (
              <p className="text-sm text-muted-foreground">Aucune donnée.</p>
            ) : globalTop.map((entry, i) => (
              <div key={entry.user_id}
                   className={`flex items-center gap-3 p-3.5 rounded-xl border transition-all duration-200 hover:border-primary/30 ${
                     i === 0 ? 'border-gold/30 bg-gold/5' : 'border-border bg-card'
                   }`}
              >
                <span className={`text-lg font-bold w-8 text-center flex-shrink-0 ${
                  i === 0 ? 'text-2xl' : ''
                }`}>
                  {medals[i] ?? `${i + 1}`}
                </span>
                {entry.discord_avatar ? (
                  <img src={entry.discord_avatar} alt={entry.username}
                       className={`rounded-full flex-shrink-0 ${i === 0 ? 'w-10 h-10 ring-2 ring-gold/40' : 'w-8 h-8'}`} />
                ) : (
                  <div className={`rounded-full bg-accent flex items-center justify-center font-bold flex-shrink-0 ${
                    i === 0 ? 'w-10 h-10 text-base' : 'w-8 h-8 text-sm'
                  }`}>
                    {entry.username[0]?.toUpperCase()}
                  </div>
                )}
                <div className="flex-1 min-w-0">
                  <p className={`font-medium truncate ${i === 0 ? 'text-base' : 'text-sm'}`}>
                    {entry.username}
                  </p>
                  <p className="text-xs text-muted-foreground truncate">
                    {entry.voice_formatted} · {entry.total_messages.toLocaleString()} msgs · {entry.achievement_count} 🏆
                  </p>
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  )
}
