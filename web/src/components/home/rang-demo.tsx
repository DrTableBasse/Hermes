import { Hash } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Chip } from "@/components/ui/chip"
import { DiscordEmbed, DiscordMessage, DiscordWindow } from "@/components/ui/discord-window"
import { SectionHeading } from "@/components/ui/section-heading"
import { XpBar } from "@/components/ui/xp-bar"
import type { Grade, HermesStatus } from "@/lib/api/types"
import { cn } from "@/lib/cn"
import { formatNumber, formatSince, xpProgress } from "@/lib/format"
import { gradeForLevel } from "@/components/home/hero"

// Réponse d'exemple à `/rang` : membre, XP et classement inventés (pastille « Exemple »).
const DEMO_NAME = "Chipolata"
const DEMO_XP = 45_715

const percent = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 2 })

function StatusPill({ status }: { status: HermesStatus }) {
  const tone = status.stale ? "orange" : status.online ? "green" : "muted"
  const label = status.stale
    ? "Statut d’Hermes incertain"
    : status.online
      ? "Hermes est en ligne"
      : "Hermes fait une sieste"
  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm font-semibold",
        tone === "green" && "border-green/40 bg-green/12 text-green",
        tone === "orange" && "border-orange/40 bg-orange/10 text-orange",
        tone === "muted" && "border-white/14 bg-white/6 text-muted",
      )}
    >
      <i
        className={cn("size-2 rounded-full bg-current", tone === "green" && "motion-safe:animate-pulse-ring")}
        aria-hidden="true"
      />
      {label}
    </span>
  )
}

function availabilityText(a: HermesStatus["availability"]): string {
  if (a.percent !== null) return `${percent.format(a.percent)} %`
  return a.since ? formatSince(a.since).replace(/^d/, "D") : "—"
}

function Figures({ status }: { status: HermesStatus }) {
  const items: Array<[string, string]> = [
    [status.latency_ms === null ? "—" : `${formatNumber(Math.round(status.latency_ms))} ms`, "de réponse"],
    [availabilityText(status.availability), status.availability.percent === null ? "en service" : "disponible sur 30 jours"],
    [status.commands_served === null ? "—" : formatNumber(status.commands_served), "commandes servies"],
  ]
  return (
    <dl className="mt-5 grid max-w-[460px] grid-cols-3 gap-2.5 max-[480px]:grid-cols-1" data-testid="hermes-figures">
      {items.map(([value, label]) => (
        <div key={label} className="flex flex-col-reverse rounded-xl border border-line bg-[rgb(12_14_26/0.55)] px-3 py-2.5">
          <dt className="text-xs text-muted">{label}</dt>
          <dd className="m-0 font-display text-xl font-bold tabular-nums">{value}</dd>
        </div>
      ))}
    </dl>
  )
}

/** Aperçu d'Hermes : statut réel (s'il est connu) et démonstration de `/rang`, marquée « Exemple ». */
export function RangDemo({ status, grades }: { status: HermesStatus | null; grades: Grade[] | null }) {
  const progress = xpProgress(DEMO_XP)
  const grade = gradeForLevel(grades, progress.level)
  const remaining = progress.next - DEMO_XP

  return (
    <section className="relative pt-10 pb-24" aria-labelledby="hermes-title">
      <div className="relative mx-auto grid max-w-[1440px] grid-cols-[minmax(0,1fr)_minmax(0,1fr)] items-center gap-10 px-6 max-[1000px]:grid-cols-[minmax(0,1fr)] min-[1100px]:px-20">
        <div>
          <SectionHeading
            id="hermes-title"
            title="Hermes veille sur la caserne"
            sub="XP, grades, tickets, rappels de bump : notre bot s’occupe de tout. Il ne dort jamais. Il ne s’en plaint pas. Enfin, pas trop."
            lead={status ? <StatusPill status={status} /> : undefined}
          />
          {status && <Figures status={status} />}
          <Button href="/hermes" variant="ghost" className="mt-6 px-5 py-3 text-[15px]">
            Ouvrir le tableau de bord d’Hermes
          </Button>
        </div>

        <div className="relative grid w-full max-w-[520px] gap-3 justify-self-end max-[1000px]:justify-self-start" data-testid="rang-demo">
          <Chip example className="justify-self-end">
            Exemple
          </Chip>
          <DiscordWindow title="commandes-bot" icon={<Hash />}>
            <DiscordMessage author={DEMO_NAME} avatarColor="#4F6FB8" nameColor="#8FB1FF" time="21:12">
              <code className="font-mono text-sm font-semibold text-cyan">/rang</code>
            </DiscordMessage>
            <DiscordMessage author="Hermes" avatarColor="var(--color-violet)" nameColor="#C9B5FF" time="21:12" bot>
              <DiscordEmbed title={grade ? `${DEMO_NAME}, ${grade.name}` : DEMO_NAME} accent={grade?.color ?? "var(--color-cyan)"}>
                <p className="m-0">
                  Niveau {progress.level}, {formatNumber(DEMO_XP)} XP. 2e du classement de la semaine. Série de 14 jours.
                </p>
                <XpBar ratio={progress.ratio} label={`Progression de ${DEMO_NAME} vers le niveau ${progress.level + 1}`} />
                <p className="m-0 text-muted">
                  Encore {formatNumber(remaining)} XP avant le niveau {progress.level + 1}. Courage. Ou pas, je ne juge pas.
                </p>
              </DiscordEmbed>
            </DiscordMessage>
          </DiscordWindow>
        </div>
      </div>
    </section>
  )
}
