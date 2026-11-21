import type { Metadata } from "next"
import Link from "next/link"
import { StreakBadge } from "@/components/account/streak-badge"
import { AchievementsPanel } from "@/components/members/achievements-panel"
import { StaffProfileForm } from "@/components/staff/staff-profile-form"
import { Avatar } from "@/components/ui/avatar"
import { GradeBadge } from "@/components/ui/grade-badge"
import { Panel } from "@/components/ui/panel"
import { SectionHeading } from "@/components/ui/section-heading"
import { XpBar } from "@/components/ui/xp-bar"
import {
  getGames,
  getSessionUser,
  getStaff,
  getUserAchievementsAll,
  getUserStats,
  getXp,
} from "@/lib/api/server"
import type { UserStats, XpData } from "@/lib/api/types"
import { formatDate, formatNumber, xpProgress } from "@/lib/format"
import { sessionToken } from "@/lib/session"

export const metadata: Metadata = {
  title: "Profil · SaucisseLand",
}

function Note({ children }: { children: React.ReactNode }) {
  return (
    <p className="mt-8 mb-0 rounded-2xl border border-line bg-[rgb(19_22_42/0.6)] px-6 py-5 text-muted" role="status">
      {children}
    </p>
  )
}

function voiceTime(hours: number): string {
  const h = Math.floor(hours)
  const m = Math.round((hours - h) * 60)
  return m === 60 ? `${h + 1} h 00` : `${h} h ${String(m).padStart(2, "0")}`
}

function statCards(stats: UserStats["stats"]): Array<{ label: string; value: string; sub: string }> {
  const voice = stats.current_streak
  const msgs = stats.msg_current_streak ?? 0
  return [
    { label: "Messages", value: formatNumber(stats.total_messages), sub: `n° ${formatNumber(stats.msg_rank)}` },
    { label: "Temps vocal", value: voiceTime(stats.voice_hours), sub: `n° ${formatNumber(stats.voice_rank)}` },
    {
      label: "Avertissements",
      value: formatNumber(stats.warn_count),
      sub: stats.warn_count === 0 ? "Casier vierge" : "Actifs",
    },
    {
      label: "Bumps",
      value: formatNumber(stats.bump_count ?? 0),
      sub: stats.bump_rank ? `n° ${formatNumber(stats.bump_rank)}` : "Pas encore classé",
    },
    {
      label: "Série en vocal",
      value: voice > 0 ? `${voice} j` : "—",
      sub: voice > 0 ? `×${(stats.xp_multiplier ?? 1).toFixed(1)} XP · record ${stats.max_streak ?? 0} j` : "Rejoins un vocal",
    },
    {
      label: "Série en messages",
      value: msgs > 0 ? `${msgs} j` : "—",
      sub: msgs > 0 ? `record ${stats.msg_max_streak ?? 0} j` : "Envoie un message",
    },
  ]
}

function Overview({ data, xp }: { data: UserStats; xp: XpData | null }) {
  const { user, stats } = data
  const name = user.nickname ?? user.username
  const progress = xpProgress(stats.xp_total)
  const level = xp?.current_level ?? stats.current_level
  return (
    <>
      <Panel className="flex flex-wrap items-center gap-5">
        <Avatar name={name} src={user.discord_avatar} size={80} ring={xp?.grade.color} labelled />
        <div className="min-w-0 flex-1">
          <h2 className="m-0 font-display text-3xl leading-tight font-extrabold break-words">{name}</h2>
          {user.nickname && <p className="m-0 text-muted">@{user.username}</p>}
          <p className="mt-2 mb-0 flex flex-wrap items-center gap-2">
            {xp && <GradeBadge grade={xp.grade} />}
            <span className="text-sm text-muted tabular-nums">niveau {formatNumber(level)}</span>
            <StreakBadge streak={stats.current_streak} />
          </p>
          {user.last_seen && <p className="mt-1 mb-0 text-xs text-muted">Vu le {formatDate(user.last_seen)}</p>}
        </div>
        <Link
          href={`/u/${encodeURIComponent(user.user_id)}`}
          className="text-sm font-semibold text-cyan hover:underline"
        >
          Voir mon profil public
        </Link>
      </Panel>
      <div className="mt-4">
        <XpBar ratio={progress.ratio} height={10} sausage label={`Progression vers le niveau ${progress.level + 1}`} />
        <p className="mt-2 mb-0 text-sm text-muted tabular-nums">
          {formatNumber(stats.xp_total)} XP · {formatNumber(Math.max(0, progress.next - stats.xp_total))} XP avant le niveau{" "}
          {progress.level + 1}
        </p>
      </div>
      <section aria-labelledby="stats-title" className="mt-10">
        <SectionHeading as="h2" id="stats-title" title="Statistiques" className="[&_h2]:text-3xl" />
        <dl className="m-0 mt-5 grid grid-cols-3 gap-4 max-[700px]:grid-cols-2">
          {statCards(stats).map(c => (
            <Panel key={c.label} className="p-5">
              <dd className="m-0 font-display text-2xl font-extrabold tabular-nums">{c.value}</dd>
              <dt className="mt-1 text-sm text-muted">{c.label}</dt>
              <dd className="m-0 mt-1.5 text-xs font-medium text-cyan">{c.sub}</dd>
            </Panel>
          ))}
        </dl>
      </section>
    </>
  )
}

/**
 * Profil du membre connecté : fiche, statistiques, succès, puis sa carte de l'état-major s'il est du
 * staff. `src/proxy.ts` renvoie déjà à l'accueil sans session.
 */
export default async function ProfilePage() {
  const token = await sessionToken()
  const [me, staff, games] = token
    ? await Promise.all([getSessionUser(token), getStaff(token), getGames()])
    : [null, null, null]
  // Données personnelles : lues avec la session, jamais en cache. Chaque bloc tolère son échec.
  const [stats, xp, achievements] =
    token && me
      ? await Promise.all([
          getUserStats(me.user_id, token).catch(() => null),
          getXp(me.user_id, token).catch(() => null),
          getUserAchievementsAll(me.user_id).catch(() => null),
        ])
      : [null, null, null]
  const mine = me && staff ? staff.staff.find(m => m.id === me.user_id) : undefined

  return (
    <main className="relative pt-10 pb-24">
      <div className="relative mx-auto max-w-[1440px] px-6 min-[1100px]:px-20">
        <SectionHeading as="h1" title="Ton profil" />
        {me && (
          <div className="mt-10">
            {stats ? (
              <Overview data={stats} xp={xp} />
            ) : (
              <Note>Tes statistiques sont injoignables pour l’instant. Hermes recompte, reviens dans un moment.</Note>
            )}
          </div>
        )}
        {me && achievements && achievements.length > 0 && (
          <section aria-labelledby="achievements-title" className="mt-10">
            <SectionHeading as="h2" id="achievements-title" title="Tes succès" className="[&_h2]:text-3xl" />
            <div className="mt-5">
              <AchievementsPanel achievements={achievements} />
            </div>
          </section>
        )}
        {/* Liste périmée : phrase et jeux peuvent y être vides (base illisible). Préremplir le formulaire
            avec ce vide ferait écraser le vrai profil au premier « Enregistrer » : pas de formulaire. */}
        {me && staff?.stale ? (
          <Note>Hermes est injoignable pour l’instant, ta carte ne peut pas être modifiée. Réessaie plus tard.</Note>
        ) : mine ? (
          <section
            aria-labelledby="staff-card-title"
            className="mt-10 max-w-[760px] rounded-[22px] border border-white/9 bg-[rgb(19_22_42/0.9)] p-7"
          >
            <h2 id="staff-card-title" className="m-0 font-display text-2xl font-bold">
              Ta carte de l’état-major
            </h2>
            <p className="mt-2 mb-7 text-muted">
              Ce que les recrues voient de toi sur la page de l’état-major. Ton rôle et ton grade viennent du Discord.
            </p>
            {/* Liste périmée (base illisible) : vide, elle ferait croire qu'aucun jeu n'existe. */}
            <StaffProfileForm motto={mine.motto} selected={mine.games} games={games && !games.stale ? games.games : null} />
          </section>
        ) : !me || !staff ? (
          <Note>Ton profil est injoignable pour l’instant. Reviens dans un moment.</Note>
        ) : null}
      </div>
    </main>
  )
}
