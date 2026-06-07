import React from 'react'
import { headers } from 'next/headers'
import Link from 'next/link'
import { auth } from '@/lib/auth'
import { Suspense } from 'react'
import {
  serverLeaderboardVoice,
  serverLeaderboardMessages,
  serverLeaderboardAchievements,
  serverLeaderboardBumps,
  serverLeaderboardInvites,
  serverLeaderboardLevels,
  serverLeaderboardStreaks,
  serverMyRanks,
  type LbPage,
  type AchievementEntry,
  type BumpEntry,
  type InviteEntry,
  type LevelEntry,
  type StreakEntry,
  type MyRanks,
} from '@/lib/server-api'
import type { VoiceEntry, LeaderboardEntry } from '@/lib/api'
import { LeaderboardSearch } from './LeaderboardSearch'

const LIMIT = 10
const TABS  = ['voice', 'messages', 'achievements', 'bumps', 'invites', 'levels', 'streaks'] as const
type Tab    = typeof TABS[number]

type UserWithExtras = { discordId?: string } & Record<string, unknown>

function tabLabel(tab: Tab) {
  if (tab === 'voice')        return '🎤 Vocal'
  if (tab === 'messages')     return '💬 Messages'
  if (tab === 'achievements') return '🏆 Succès'
  if (tab === 'bumps')        return '📈 Bumps'
  if (tab === 'invites')      return '🤝 Invitations'
  if (tab === 'streaks')      return '🔥 Streaks'
  return '⚡ Niveaux'
}

function scoreLabel(tab: Tab, entry: any): string {
  if (tab === 'voice')        return entry.formatted
  if (tab === 'messages')     return `${Number(entry.total_messages).toLocaleString()} msgs`
  if (tab === 'bumps')        return `${Number(entry.bump_count).toLocaleString()} bumps`
  if (tab === 'invites')      return `${Number(entry.invite_count).toLocaleString()} invitations`
  if (tab === 'levels')       return `${Number(entry.total_xp).toLocaleString()} XP`
  if (tab === 'streaks')      return `🔥 ${entry.current_streak}j · ×${Number(entry.xp_multiplier).toFixed(1)}`
  return `${entry.achievement_count} succès`
}

function Avatar({ src, name, size = 'md' }: { src: string | null; name: string; size?: 'sm' | 'md' | 'lg' }) {
  const sizes = { sm: 'w-8 h-8 text-xs', md: 'w-10 h-10 text-sm', lg: 'w-14 h-14 text-lg' }
  return src ? (
    <img src={src} alt={name} className={`${sizes[size]} rounded-full flex-shrink-0`} />
  ) : (
    <div className={`${sizes[size]} rounded-full bg-accent flex items-center justify-center font-bold flex-shrink-0`}>
      {name[0]?.toUpperCase()}
    </div>
  )
}

function medal(rank: number) {
  if (rank === 1) return '🥇'
  if (rank === 2) return '🥈'
  if (rank === 3) return '🥉'
  return rank
}

export default async function LeaderboardPage({
  params,
  searchParams,
}: {
  params: Promise<{ locale: string }>
  searchParams: Promise<{ tab?: string; page?: string; hl?: string; q?: string }>
}) {
  const { locale }         = await params
  const { tab: rawTab, page: rawPage, hl, q } = await searchParams
  const search = q?.trim() || undefined
  const tab  = (TABS.includes(rawTab as Tab) ? rawTab : 'voice') as Tab
  const page = Math.max(1, parseInt(rawPage ?? '1', 10))

  const session = await auth.api.getSession({ headers: await headers() }).catch(() => null)
  const u = session?.user as UserWithExtras | undefined
  const token = session ? (session.session as any).token as string : undefined
  const myDiscordId = u?.discordId ?? null

  type LbResult = LbPage<VoiceEntry> | LbPage<LeaderboardEntry> | LbPage<AchievementEntry> | LbPage<BumpEntry> | LbPage<InviteEntry> | LbPage<LevelEntry> | LbPage<StreakEntry>
  const [lbData, myRanks] = await Promise.all([
    (tab === 'voice'
      ? serverLeaderboardVoice(page, LIMIT, search)
      : tab === 'messages'
      ? serverLeaderboardMessages(page, LIMIT, search)
      : tab === 'bumps'
      ? serverLeaderboardBumps(page, LIMIT, search)
      : tab === 'invites'
      ? serverLeaderboardInvites(page, LIMIT, search)
      : tab === 'levels'
      ? serverLeaderboardLevels(page, LIMIT, search)
      : tab === 'streaks'
      ? serverLeaderboardStreaks(page, LIMIT, search)
      : serverLeaderboardAchievements(page, LIMIT, search)
    ).catch((): LbResult => ({ leaderboard: [], total: 0, page, limit: LIMIT })),
    token ? serverMyRanks(token).catch((): MyRanks | null => null) : Promise.resolve(null),
  ])

  const { leaderboard, total } = lbData
  const totalPages = Math.max(1, Math.ceil(total / LIMIT))

  let jumpUrl: string | null = null
  if (myRanks && myDiscordId) {
    const myRank = tab === 'voice'
      ? myRanks.voice_rank
      : tab === 'messages'
      ? myRanks.messages_rank
      : tab === 'bumps'
      ? myRanks.bumps_rank
      : tab === 'invites'
      ? myRanks.invites_rank
      : tab === 'levels'
      ? myRanks.level_rank
      : tab === 'streaks'
      ? myRanks.streak_rank
      : myRanks.achievements_rank
    const myPage = Math.ceil(myRank / LIMIT)
    jumpUrl = `/${locale}/leaderboard?tab=${tab}&page=${myPage}&hl=${myDiscordId}`
  }

  function href(overrides: { tab?: Tab; page?: number }) {
    const t = overrides.tab  ?? tab
    const p = overrides.page ?? 1
    const qs = new URLSearchParams({ tab: t, page: String(p) })
    if (search) qs.set('q', search)
    return `/${locale}/leaderboard?${qs}`
  }

  const top3 = page === 1 && !search ? (leaderboard as any[]).slice(0, 3) : []
  const rest = page === 1 && !search ? (leaderboard as any[]).slice(3) : (leaderboard as any[])
  const restStartRank = page === 1 && !search ? 4 : (page - 1) * LIMIT + 1

  return (
    <div className="container mx-auto px-4 py-12 max-w-2xl">
      <div className="flex flex-wrap items-center justify-between gap-4 mb-8">
        <h1 className="text-3xl font-extrabold tracking-tight">Classement</h1>
        <div className="flex items-center gap-3">
          <Suspense><LeaderboardSearch defaultValue={q ?? ''} /></Suspense>
          {jumpUrl && (
            <Link
              href={jumpUrl}
              className="px-4 py-2 text-sm font-medium bg-primary text-primary-foreground rounded-lg hover:opacity-90 transition-opacity"
            >
              Mon classement
            </Link>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-8 bg-secondary/60 rounded-xl p-1 backdrop-blur-sm">
        {TABS.map(t => (
          <Link
            key={t}
            href={href({ tab: t })}
            className={`flex-1 text-center py-2.5 px-3 text-sm font-medium rounded-lg transition-all ${
              t === tab
                ? 'bg-background text-foreground shadow-sm'
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            {tabLabel(t)}
          </Link>
        ))}
      </div>

      {search && (
        <p className="text-sm text-muted-foreground mb-4">
          {total} résultat{total > 1 ? 's' : ''} pour «&nbsp;<strong className="text-foreground">{search}</strong>&nbsp;»
        </p>
      )}

      {/* Top 3 Podium */}
      {top3.length >= 3 && (
        <>
          {/* Mobile layout — visible only on xs screens */}
          <div className="block sm:hidden mb-8 space-y-3">
            {/* #1 Gold — full width, prominent */}
            <div className="flex flex-col items-center text-center p-5 rounded-2xl border border-gold/40 bg-gold/5 medal-glow">
              <span className="text-4xl font-bold mb-2">{medal(1)}</span>
              <Avatar src={top3[0].discord_avatar} name={top3[0].username} size="lg" />
              <p className="font-semibold text-base w-full mt-2">{top3[0].username}</p>
              {tab === 'levels' && (
                <p className="font-bold mt-1 text-base text-primary">
                  Niv.&nbsp;{top3[0].current_level}
                </p>
              )}
              {tab === 'streaks' && (
                <p className="font-bold mt-1 text-base text-primary">
                  Record&nbsp;{top3[0].max_streak}j
                </p>
              )}
              <p className="text-xs text-muted-foreground mt-0.5 tabular-nums">
                {scoreLabel(tab, top3[0])}
              </p>
            </div>

            {/* #2 Silver + #3 Bronze — side by side */}
            <div className="grid grid-cols-2 gap-3">
              {[top3[1], top3[2]].map((entry, i) => {
                const actualRank = i === 0 ? 2 : 3
                return (
                  <div key={entry.user_id}
                       className="flex flex-col items-center text-center p-3 rounded-2xl border border-border bg-card"
                  >
                    <span className="text-xl font-bold mb-2">{medal(actualRank)}</span>
                    <Avatar src={entry.discord_avatar} name={entry.username} size="sm" />
                    <p className="font-semibold text-xs truncate w-full mt-2">{entry.username}</p>
                    {tab === 'levels' && (
                      <p className="font-bold mt-1 text-xs text-primary/80">
                        Niv.&nbsp;{entry.current_level}
                      </p>
                    )}
                    {tab === 'streaks' && (
                      <p className="font-bold mt-1 text-xs text-primary/80">
                        Record&nbsp;{entry.max_streak}j
                      </p>
                    )}
                    <p className="text-xs text-muted-foreground mt-0.5 tabular-nums">
                      {scoreLabel(tab, entry)}
                    </p>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Desktop layout — visible on sm+ screens */}
          <div className="hidden sm:grid grid-cols-3 gap-3 mb-8">
            {[top3[1], top3[0], top3[2]].map((entry, i) => {
              const actualRank = [2, 1, 3][i]
              const isCenter = i === 1
              return (
                <div key={entry.user_id}
                     className={`flex flex-col items-center text-center p-4 rounded-2xl border transition-all ${
                       isCenter
                         ? 'border-gold/40 bg-gold/5 -mt-4 pb-6 medal-glow'
                         : 'border-border bg-card mt-2'
                     }`}
                >
                  <span className={`font-bold mb-2 ${isCenter ? 'text-3xl' : 'text-2xl'}`}>
                    {medal(actualRank)}
                  </span>
                  <Avatar src={entry.discord_avatar} name={entry.username} size={isCenter ? 'lg' : 'md'} />
                  <p className={`font-semibold truncate w-full mt-2 ${isCenter ? 'text-base' : 'text-sm'}`}>
                    {entry.username}
                  </p>
                  {tab === 'levels' && (
                    <p className={`font-bold mt-1 ${isCenter ? 'text-base text-primary' : 'text-sm text-primary/80'}`}>
                      Niv.&nbsp;{entry.current_level}
                    </p>
                  )}
                  {tab === 'streaks' && (
                    <p className={`font-bold mt-1 ${isCenter ? 'text-base text-primary' : 'text-sm text-primary/80'}`}>
                      Record&nbsp;{entry.max_streak}j
                    </p>
                  )}
                  <p className="text-xs text-muted-foreground mt-0.5 tabular-nums">
                    {scoreLabel(tab, entry)}
                  </p>
                </div>
              )
            })}
          </div>
        </>
      )}

      {/* Rest of leaderboard */}
      <div className="space-y-2 mb-6">
        {leaderboard.length === 0 ? (
          <p className="text-center text-muted-foreground py-10">Aucune donnée disponible.</p>
        ) : rest.map((entry: any, i: number) => {
          const globalRank = entry.global_rank ?? restStartRank + i
          const isMe = myDiscordId && entry.user_id === myDiscordId
          const highlighted = hl && entry.user_id === hl

          return (
            <div
              key={entry.user_id}
              className={`flex items-center gap-3 p-3.5 rounded-xl border transition-all ${
                highlighted
                  ? 'border-primary bg-primary/10'
                  : isMe
                  ? 'border-primary/40 bg-primary/5'
                  : 'border-border bg-card hover:border-border/80'
              }`}
            >
              <span className="w-10 text-center font-bold text-lg flex-shrink-0 tabular-nums text-muted-foreground">
                {medal(globalRank)}
              </span>
              <Avatar src={entry.discord_avatar} name={entry.username} />
              <span className="flex-1 font-medium truncate">
                {entry.username}
                {isMe && (
                  <span className="ml-2 text-xs text-primary font-normal">(moi)</span>
                )}
              </span>
              {tab === 'levels' && (
                <span className="shrink-0 mr-2 px-2 py-0.5 rounded-full text-xs font-bold bg-primary/15 text-primary border border-primary/30">
                  Niv.&nbsp;{entry.current_level}
                </span>
              )}
              {tab === 'streaks' && (
                <span className="shrink-0 mr-2 px-2 py-0.5 rounded-full text-xs font-bold bg-orange-500/15 text-orange-400 border border-orange-500/30">
                  ×{Number(entry.xp_multiplier).toFixed(1)}
                </span>
              )}
              <span className="text-sm text-muted-foreground tabular-nums flex-shrink-0">
                {scoreLabel(tab, entry)}
              </span>
            </div>
          )
        })}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-1 flex-wrap">
          <Link
            href={href({ page: Math.max(1, page - 1) })}
            prefetch={false}
            className={`px-3 py-1.5 text-sm rounded-lg border transition-colors ${
              page === 1
                ? 'border-border text-muted-foreground/40 pointer-events-none'
                : 'border-border text-muted-foreground hover:text-foreground hover:border-primary/30'
            }`}
          >
            ‹
          </Link>

          {(() => {
            const visible = new Set<number>()
            visible.add(1)
            visible.add(totalPages)
            for (let p = Math.max(1, page - 2); p <= Math.min(totalPages, page + 2); p++) visible.add(p)
            const sorted = Array.from(visible).sort((a, b) => a - b)
            const nodes: React.ReactNode[] = []
            for (let i = 0; i < sorted.length; i++) {
              const prev = sorted[i - 1]
              const p = sorted[i]
              if (i > 0 && p - prev === 2) {
                const mid = prev + 1
                nodes.push(
                  <Link key={mid} href={href({ page: mid })} prefetch={false}
                    className="w-9 h-9 flex items-center justify-center text-sm rounded-lg border transition-all border-border text-muted-foreground hover:text-foreground hover:border-primary/30">
                    {mid}
                  </Link>
                )
              } else if (i > 0 && p - prev > 2) {
                nodes.push(<span key={`el-${i}`} className="px-1 text-muted-foreground">…</span>)
              }
              nodes.push(
                <Link key={p} href={href({ page: p })} prefetch={false}
                  className={`w-9 h-9 flex items-center justify-center text-sm rounded-lg border transition-all ${
                    p === page
                      ? 'border-primary text-primary bg-primary/10'
                      : 'border-border text-muted-foreground hover:text-foreground hover:border-primary/30'
                  }`}>
                  {p}
                </Link>
              )
            }
            return nodes
          })()}

          <Link
            href={href({ page: Math.min(totalPages, page + 1) })}
            prefetch={false}
            className={`px-3 py-1.5 text-sm rounded-lg border transition-colors ${
              page === totalPages
                ? 'border-border text-muted-foreground/40 pointer-events-none'
                : 'border-border text-muted-foreground hover:text-foreground hover:border-primary/30'
            }`}
          >
            ›
          </Link>
        </div>
      )}
    </div>
  )
}
