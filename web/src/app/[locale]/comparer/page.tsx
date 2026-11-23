import type { Metadata } from "next"
import { Avatar } from "@/components/ui/avatar"
import { GradeBadge } from "@/components/ui/grade-badge"
import { Panel } from "@/components/ui/panel"
import { SectionHeading } from "@/components/ui/section-heading"
import { getUserPublicStats } from "@/lib/api/server"
import type { PublicUserStats } from "@/lib/api/types"
import { cn } from "@/lib/cn"
import { formatNumber } from "@/lib/format"
import { firstParam, isSnowflake, isUnknownMember } from "@/lib/members"

export const metadata: Metadata = {
  title: "Comparer des membres · SaucisseLand",
  description: "Deux membres face à face : niveau, XP, messages, vocal, succès, série et bumps.",
}

type Param = string | string[] | undefined
type Props = { searchParams: Promise<{ u1?: Param; u2?: Param }> }

type Loaded = { user: PublicUserStats } | { missing: true } | { down: true }

async function load(id: string): Promise<Loaded> {
  if (!isSnowflake(id)) return { missing: true }
  try {
    return { user: await getUserPublicStats(id) }
  } catch (error) {
    return isUnknownMember(error) ? { missing: true } : { down: true }
  }
}

function Message({ children }: { children: React.ReactNode }) {
  return (
    <main className="relative pt-10 pb-24">
      <div className="relative mx-auto max-w-[900px] px-6">
        <SectionHeading as="h1" title="Comparer des membres" />
        <Panel className="mt-8 text-center text-muted" role="status">
          {children}
        </Panel>
      </div>
    </main>
  )
}

function Head({ user }: { user: PublicUserStats }) {
  const name = user.nickname ?? user.username
  return (
    <div className="flex flex-col items-center gap-2 p-4 text-center">
      <Avatar name={name} src={user.discord_avatar} size={64} ring={user.stats.grade.color} labelled />
      <p className="m-0 font-display font-bold break-words">{name}</p>
      {user.nickname && <p className="m-0 text-xs text-muted">@{user.username}</p>}
      <GradeBadge grade={user.stats.grade} />
    </div>
  )
}

function Row({ label, v1, v2 }: { label: string; v1: number | string; v2: number | string }) {
  const n1 = typeof v1 === "number" ? v1 : null
  const n2 = typeof v2 === "number" ? v2 : null
  const win1 = n1 !== null && n2 !== null && n1 > n2
  const win2 = n1 !== null && n2 !== null && n2 > n1
  const show = (v: number | string) => (typeof v === "number" ? formatNumber(v) : v)
  return (
    <tr className="border-b border-white/5 last:border-b-0">
      <td data-win={win1 ? "true" : undefined} className={cn("px-3 py-3 text-right font-semibold tabular-nums", win1 && "text-green")}>
        {show(v1)}
      </td>
      <th scope="row" className="px-3 py-3 text-center text-xs font-normal whitespace-nowrap text-muted">
        {label}
      </th>
      <td data-win={win2 ? "true" : undefined} className={cn("px-3 py-3 text-left font-semibold tabular-nums", win2 && "text-green")}>
        {show(v2)}
      </td>
    </tr>
  )
}

export default async function ComparePage({ searchParams }: Props) {
  const sp = await searchParams
  const u1 = firstParam(sp.u1)
  const u2 = firstParam(sp.u2)

  if (!u1 || !u2) {
    return (
      <Message>
        <p className="mt-0">Passe les identifiants Discord de deux membres dans l’adresse :</p>
        <code className="inline-block rounded-lg bg-white/5 px-3 py-2 font-mono text-sm text-cyan">
          /comparer?u1=&lt;identifiant 1&gt;&amp;u2=&lt;identifiant 2&gt;
        </code>
      </Message>
    )
  }

  const [r1, r2] = await Promise.all([load(u1), load(u2)])

  if (!("user" in r1) || !("user" in r2)) {
    if ("down" in r1 || "down" in r2) {
      return <Message>Hermes ne répond pas : impossible de comparer pour l’instant. Réessaie dans un moment.</Message>
    }
    const m1 = "missing" in r1
    const m2 = "missing" in r2
    return (
      <Message>{m1 && m2 ? "Aucun des deux membres n’a été trouvé." : `Membre ${m1 ? u1 : u2} introuvable.`}</Message>
    )
  }

  const a = r1.user
  const b = r2.user
  return (
    <main className="relative pt-10 pb-24">
      <div className="relative mx-auto max-w-[900px] px-6">
        <SectionHeading as="h1" title="Comparaison" />
        <Panel className="mt-8 overflow-hidden p-0">
          <div className="grid grid-cols-[1fr_auto_1fr] items-center border-b border-line">
            <Head user={a} />
            <span className="px-2 font-display text-2xl font-black text-muted" aria-hidden="true">
              VS
            </span>
            <Head user={b} />
          </div>
          <table className="w-full border-collapse">
            <caption className="sr-only">
              {a.nickname ?? a.username} contre {b.nickname ?? b.username}
            </caption>
            <tbody>
              <Row label="Niveau" v1={a.stats.current_level} v2={b.stats.current_level} />
              <Row label="XP total" v1={a.stats.total_xp} v2={b.stats.total_xp} />
              <Row label="Messages" v1={a.stats.total_messages} v2={b.stats.total_messages} />
              <Row label="Temps vocal" v1={a.stats.voice_formatted} v2={b.stats.voice_formatted} />
              <Row label="Succès" v1={a.stats.achievement_count} v2={b.stats.achievement_count} />
              <Row label="Série actuelle" v1={a.stats.current_streak} v2={b.stats.current_streak} />
              <Row label="Bumps" v1={a.stats.bump_count} v2={b.stats.bump_count} />
            </tbody>
          </table>
        </Panel>
      </div>
    </main>
  )
}
