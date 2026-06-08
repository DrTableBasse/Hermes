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

  const discordInviteUrl = process.env.NEXT_PUBLIC_DISCORD_INVITE_URL
  const isSafeDiscordUrl = discordInviteUrl?.startsWith('https://')

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
          <div className="animate-fade-up flex flex-col items-center gap-5" style={{ animationDelay: '0.2s' }}>
            {/* Feature badges */}
            <div className="flex flex-wrap justify-center gap-2">
              <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-border bg-card text-sm font-medium text-foreground">
                🎮 {t('badge_gaming')}
              </span>
              <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-border bg-card text-sm font-medium text-foreground">
                🏆 {t('badge_leaderboard')}
              </span>
              <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-border bg-card text-sm font-medium text-foreground">
                🔥 {t('badge_quests')}
              </span>
            </div>

            {/* Primary Discord CTA */}
            {isSafeDiscordUrl && (
              <a
                href={discordInviteUrl!}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2.5 py-3 px-6 rounded-xl text-white font-bold text-lg shadow-lg transition-opacity hover:opacity-90 bg-discord"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="white">
                  <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057.102 18.08.116 18.1.133 18.113a19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028c.462-.63.874-1.295 1.226-1.994a.076.076 0 0 0-.041-.106 13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.892.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03z"/>
                </svg>
                {t('join_discord')}
              </a>
            )}

            {/* Discrete login link */}
            <LoginButton
              callbackURL={`/${locale}`}
              label={t('already_member')}
              className="text-sm text-muted-foreground hover:text-foreground transition-colors cursor-pointer bg-transparent border-0 p-0"
              iconClassName="hidden"
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
