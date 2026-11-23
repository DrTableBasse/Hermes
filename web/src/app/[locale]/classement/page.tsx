import type { Metadata } from "next"
import Link from "next/link"
import { Suspense } from "react"
import { RankPagination } from "@/components/members/rank-pagination"
import { RankSearch } from "@/components/members/rank-search"
import { RankTable } from "@/components/members/rank-table"
import { Avatar } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import { GradeBadge } from "@/components/ui/grade-badge"
import { Panel } from "@/components/ui/panel"
import { SectionHeading } from "@/components/ui/section-heading"
import {
  getSessionUser,
  leaderboardAchievements,
  leaderboardBumps,
  leaderboardInvites,
  leaderboardLevels,
  leaderboardMessages,
  leaderboardStreaks,
  leaderboardVoice,
  myRanks,
} from "@/lib/api/server"
import type { LbPage, MyRanks } from "@/lib/api/types"
import { cn } from "@/lib/cn"
import {
  firstParam,
  pageOfRank,
  parsePage,
  parseTab,
  RANK_TABS,
  RANK_TAB_LABELS,
  toRankRows,
  type RankRow,
  type RankTab,
} from "@/lib/members"
import { sessionToken } from "@/lib/session"

export const metadata: Metadata = {
  title: "Classement · SaucisseLand",
  description: "Les classements de la caserne : vocal, messages, succès, bumps, invitations, niveaux et séries.",
}

const LIMIT = 10

const FETCHERS: Record<RankTab, (page: number, limit: number, search?: string) => Promise<LbPage<object>>> = {
  voice: leaderboardVoice,
  messages: leaderboardMessages,
  achievements: leaderboardAchievements,
  bumps: leaderboardBumps,
  invites: leaderboardInvites,
  levels: leaderboardLevels,
  streaks: leaderboardStreaks,
}

const MY_RANK: Record<RankTab, keyof MyRanks> = {
  voice: "voice_rank",
  messages: "messages_rank",
  achievements: "achievements_rank",
  bumps: "bumps_rank",
  invites: "invites_rank",
  levels: "level_rank",
  streaks: "streak_rank",
}

const MEDALS = ["🥇", "🥈", "🥉"]

type Param = string | string[] | undefined
type Search = { tab?: Param; page?: Param; hl?: Param; q?: Param }

function Podium({ rows }: { rows: RankRow[] }) {
  // Ordre visuel 2 · 1 · 3 ; l'ordre de lecture reste 1, 2, 3 (on ne réordonne que par CSS).
  const order = ["min-[641px]:order-2", "min-[641px]:order-1", "min-[641px]:order-3"]
  return (
    <ol className="m-0 mb-8 grid list-none grid-cols-3 items-end gap-3 p-0 max-[640px]:grid-cols-[minmax(0,1fr)]" aria-label="Podium">
      {rows.slice(0, 3).map((r, i) => (
        <li key={r.id} className={order[i]}>
          <Panel highlight={i === 0} className={cn("flex flex-col items-center gap-1.5 p-4 text-center", i === 0 && "pb-7")}>
            <span className="text-3xl" aria-hidden="true">
              {MEDALS[i]}
            </span>
            <span className="sr-only">Rang {r.rank}</span>
            <Avatar name={r.name} src={r.avatar} size={i === 0 ? 64 : 48} />
            <Link href={`/u/${encodeURIComponent(r.id)}`} className="w-full truncate font-semibold hover:text-cyan">
              {r.name}
            </Link>
            {r.grade && <GradeBadge grade={r.grade} />}
            {r.level !== null && <span className="text-sm text-muted tabular-nums">niv. {r.level}</span>}
            <span className="text-sm text-muted tabular-nums">{r.score}</span>
            {r.detail && <span className="text-sm text-orange tabular-nums">{r.detail}</span>}
          </Panel>
        </li>
      ))}
    </ol>
  )
}

export default async function ClassementPage({ searchParams }: { searchParams: Promise<Search> }) {
  const sp = await searchParams
  const q = firstParam(sp.q)
  const hl = firstParam(sp.hl)
  const tab = parseTab(firstParam(sp.tab))
  const page = parsePage(firstParam(sp.page))
  const search = q?.trim() || undefined

  const token = await sessionToken()
  const [lb, me, ranks] = await Promise.all([
    FETCHERS[tab](page, LIMIT, search).catch(() => null),
    token ? getSessionUser(token) : Promise.resolve(null),
    token ? myRanks(token).catch(() => null) : Promise.resolve(null),
  ])
  const meId = me?.user_id ?? null

  const rows = lb ? toRankRows(tab, lb.leaderboard) : []
  const total = lb?.total ?? 0
  const totalPages = Math.max(1, Math.ceil(total / LIMIT))

  const hrefFor = (overrides: { tab?: RankTab; page?: number; hl?: string; keepSearch?: boolean }) => {
    const qs = new URLSearchParams({ tab: overrides.tab ?? tab, page: String(overrides.page ?? 1) })
    if (search && overrides.keepSearch !== false) qs.set("q", search)
    if (overrides.hl) qs.set("hl", overrides.hl)
    return `/classement?${qs}`
  }

  const myRank = ranks && meId ? ranks[MY_RANK[tab]] : null
  const jumpHref = myRank && meId ? hrefFor({ page: pageOfRank(myRank, LIMIT), hl: meId, keepSearch: false }) : null

  const podium = page === 1 && !search && rows.length >= 3
  const rest = podium ? rows.slice(3) : rows

  return (
    <main className="relative pt-10 pb-24">
      <div className="relative mx-auto max-w-[1100px] px-6 min-[1100px]:px-10">
        <SectionHeading
          as="h1"
          title="Classement"
          sub="Qui parle, qui chante, qui monte. Toutes les catégories, mises à jour par Hermes."
          action={
            <div className="flex flex-wrap items-center gap-3">
              <Suspense>
                <RankSearch defaultValue={q ?? ""} />
              </Suspense>
              {jumpHref && (
                <Button href={jumpHref} variant="ghost" size="md" prefetch={false}>
                  Mon classement
                </Button>
              )}
            </div>
          }
        />

        <nav aria-label="Catégories du classement" className="mt-8 mb-8 flex flex-wrap gap-2">
          {RANK_TABS.map(t => (
            <Link
              key={t}
              href={hrefFor({ tab: t })}
              aria-current={t === tab ? "page" : undefined}
              className={cn(
                "rounded-full border px-4 py-2 text-sm font-semibold transition-colors",
                t === tab
                  ? "border-violet bg-violet/15 text-fg"
                  : "border-line text-muted hover:border-violet/40 hover:text-fg",
              )}
            >
              {RANK_TAB_LABELS[t]}
            </Link>
          ))}
        </nav>

        {search && lb && (
          <p className="mt-0 mb-4 text-sm text-muted" role="status">
            {total} résultat{total > 1 ? "s" : ""} pour «&nbsp;<strong className="text-fg">{search}</strong>&nbsp;»
          </p>
        )}

        {lb === null ? (
          <p className="rounded-2xl border border-line bg-[rgb(19_22_42/0.6)] px-6 py-5 text-muted" role="status">
            Classement indisponible pour l’instant. Hermes recompte.
          </p>
        ) : (
          <>
            {podium && <Podium rows={rows} />}
            <section aria-label={`Classement ${RANK_TAB_LABELS[tab]}`} className="overflow-hidden rounded-[20px] border border-line bg-[rgb(19_22_42/0.85)]">
              <RankTable rows={rest} meId={meId} highlightId={hl} />
            </section>
            <RankPagination page={page} totalPages={totalPages} hrefFor={p => hrefFor({ page: p })} />
          </>
        )}
      </div>
    </main>
  )
}
