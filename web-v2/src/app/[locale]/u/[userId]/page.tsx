import type { Metadata } from "next"
import { notFound } from "next/navigation"
import { AchievementsPanel } from "@/components/members/achievements-panel"
import { ActivityHeatmap } from "@/components/members/activity-heatmap"
import { Avatar } from "@/components/ui/avatar"
import { Chip } from "@/components/ui/chip"
import { GradeBadge } from "@/components/ui/grade-badge"
import { Panel } from "@/components/ui/panel"
import { SectionHeading } from "@/components/ui/section-heading"
import { getUserAchievementsAll, getUserActivity, getUserPublicStats } from "@/lib/api/server"
import type { AchievementWithStatus, PublicUserStats } from "@/lib/api/types"
import { formatNumber } from "@/lib/format"
import { isSnowflake, isUnknownMember, TIERS, tierOf } from "@/lib/members"

type Props = { params: Promise<{ userId: string }> }

/** Profil public ; `null` : membre inconnu, `Error` : web-api injoignable. */
async function loadUser(userId: string): Promise<PublicUserStats | null | Error> {
  if (!isSnowflake(userId)) return null
  try {
    return await getUserPublicStats(userId)
  } catch (error) {
    return isUnknownMember(error) ? null : error instanceof Error ? error : new Error(String(error))
  }
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { userId } = await params
  const user = await loadUser(userId)
  if (!user || user instanceof Error) return { title: "Profil introuvable · SaucisseLand" }
  const name = user.nickname ?? user.username
  const { stats } = user
  return {
    title: `${name} · SaucisseLand`,
    description: `${stats.grade.name} · niveau ${stats.current_level} · ${formatNumber(stats.total_xp)} XP · ${stats.achievement_count} succès · ${stats.voice_formatted} en vocal`,
  }
}

export default async function PublicProfilePage({ params }: Props) {
  const { userId } = await params
  const [user, activity, allAchievements] = await Promise.all([
    loadUser(userId),
    isSnowflake(userId) ? getUserActivity(userId).catch(() => []) : Promise.resolve([]),
    isSnowflake(userId) ? getUserAchievementsAll(userId).catch(() => null) : Promise.resolve(null),
  ])

  if (user === null) notFound()
  if (user instanceof Error) {
    return (
      <main className="relative pt-10 pb-24">
        <div className="relative mx-auto max-w-[1100px] px-6 min-[1100px]:px-10">
          <p className="rounded-2xl border border-line bg-[rgb(19_22_42/0.6)] px-6 py-5 text-muted" role="status">
            Ce profil est injoignable pour l’instant. Hermes recompte, reviens dans un moment.
          </p>
        </div>
      </main>
    )
  }

  const { stats } = user
  const name = user.nickname ?? user.username
  const cards = [
    { label: "Niveau", value: formatNumber(stats.current_level) },
    { label: "XP total", value: formatNumber(stats.total_xp) },
    { label: "Messages", value: formatNumber(stats.total_messages) },
    { label: "Temps vocal", value: stats.voice_formatted },
    { label: "Succès", value: formatNumber(stats.achievement_count) },
    { label: "Série", value: stats.current_streak > 0 ? `${stats.current_streak} j` : "—" },
  ]

  // Sans le détail des succès (route muette), on retombe sur les succès débloqués du profil.
  const achievements: AchievementWithStatus[] =
    allAchievements ?? user.achievements.map(a => ({ ...a, condition_type: "", unlocked: true }))

  const tierCounts = TIERS.map(t => ({
    tier: t,
    count: user.achievements.filter(a => tierOf(a.points).label === t.label).length,
  })).filter(t => t.count > 0)

  return (
    <main className="relative pt-10 pb-24">
      <div className="relative mx-auto max-w-[1100px] px-6 min-[1100px]:px-10">
        <Panel className="flex flex-wrap items-center gap-5">
          <Avatar name={name} src={user.discord_avatar} size={80} ring={stats.grade.color} labelled />
          <div className="min-w-0">
            <h1 className="m-0 font-display text-4xl leading-tight font-extrabold tracking-[-0.02em] break-words">{name}</h1>
            {user.nickname && <p className="m-0 text-muted">@{user.username}</p>}
            <p className="mt-2 mb-0 flex flex-wrap items-center gap-2">
              <GradeBadge grade={stats.grade} />
              <span className="text-sm text-muted tabular-nums">niveau {formatNumber(stats.current_level)}</span>
            </p>
          </div>
        </Panel>

        <section aria-labelledby="stats-title" className="mt-10">
          <SectionHeading as="h2" id="stats-title" title="Statistiques" className="[&_h2]:text-3xl" />
          <dl className="m-0 mt-5 grid grid-cols-3 gap-4 max-[700px]:grid-cols-2">
            {cards.map(c => (
              <Panel key={c.label} className="p-5">
                <dd className="m-0 font-display text-2xl font-extrabold tabular-nums">{c.value}</dd>
                <dt className="mt-1 text-sm text-muted">{c.label}</dt>
              </Panel>
            ))}
          </dl>
        </section>

        {activity.length > 0 && (
          <section aria-labelledby="activity-title" className="mt-10">
            <SectionHeading as="h2" id="activity-title" title="Activité" sub="Les 12 derniers mois." className="[&_h2]:text-3xl" />
            <Panel className="mt-5">
              <ActivityHeatmap data={activity} />
            </Panel>
          </section>
        )}

        {tierCounts.length > 0 && (
          <section aria-labelledby="reputation-title" className="mt-10">
            <SectionHeading as="h2" id="reputation-title" title="Réputation" className="[&_h2]:text-3xl" />
            <ul className="m-0 mt-5 flex list-none flex-wrap gap-2 p-0">
              {tierCounts.map(({ tier, count }) => (
                <li key={tier.label}>
                  <Chip color={tier.color}>
                    {tier.icon} {count} {tier.label}
                  </Chip>
                </li>
              ))}
            </ul>
          </section>
        )}

        {achievements.length > 0 && (
          <section aria-labelledby="achievements-title" className="mt-10">
            <SectionHeading as="h2" id="achievements-title" title="Succès" className="[&_h2]:text-3xl" />
            <div className="mt-5">
              <AchievementsPanel achievements={achievements} />
            </div>
          </section>
        )}
      </div>
    </main>
  )
}
