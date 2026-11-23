import { Avatar } from "@/components/ui/avatar"
import type { HermesStatus } from "@/lib/api/types"
import { cn } from "@/lib/cn"
import { formatNumber, formatSince } from "@/lib/format"

const percent = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 2 })

type Tone = "green" | "orange" | "muted"

function statusPill(status: HermesStatus | null): { tone: Tone; label: string } {
  if (!status) return { tone: "muted", label: "Hermes ne répond pas" }
  if (status.stale) return { tone: "orange", label: "Statut incertain, dernières valeurs connues" }
  return status.online ? { tone: "green", label: "En ligne" } : { tone: "muted", label: "Hors ligne, sieste en cours" }
}

function StatusPill({ status }: { status: HermesStatus | null }) {
  const { tone, label } = statusPill(status)
  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm font-semibold",
        tone === "green" && "border-green/40 bg-green/12 text-green",
        tone === "orange" && "border-orange/40 bg-orange/10 text-orange",
        tone === "muted" && "border-white/14 bg-white/6 text-muted",
      )}
      data-testid="hermes-status"
    >
      <i
        className={cn("size-2 rounded-full bg-current", tone === "green" && "motion-safe:animate-pulse-ring")}
        aria-hidden="true"
      />
      {label}
    </span>
  )
}

type TileData = { label: string; value: string; note: string; compact?: boolean }

/** Tuiles chiffrées ; une valeur absente (`null`) retire sa tuile, aucun zéro n'est inventé. */
export function statusTiles(status: HermesStatus): TileData[] {
  const tiles: TileData[] = []
  if (status.latency_ms !== null) {
    tiles.push({
      label: "Temps de réponse",
      value: `${formatNumber(Math.round(status.latency_ms))} ms`,
      note: "plus rapide qu’une saucisse qui roule",
    })
  }
  const { percent: availability, since } = status.availability
  if (availability !== null) {
    tiles.push({ label: "Disponibilité sur 30 jours", value: `${percent.format(availability)} %`, note: "relevée minute par minute" })
  } else if (since) {
    tiles.push({
      label: "Disponibilité sur 30 jours",
      value: `En service ${formatSince(since)}`,
      note: "le pourcentage viendra après 30 jours de relevés",
      compact: true,
    })
  }
  if (status.commands_served !== null) {
    tiles.push({ label: "Commandes servies", value: formatNumber(status.commands_served), note: "depuis la mise en service" })
  }
  return tiles
}

/** En-tête du tableau de bord : identité, statut et tuiles (latence, disponibilité, commandes). */
export function StatusBoard({ status }: { status: HermesStatus | null }) {
  const tiles = status ? statusTiles(status) : []
  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3.5">
          <Avatar name="Hermes" size={48} ring="var(--color-cyan)" />
          <div>
            <b className="block font-display text-[22px]">Hermes</b>
            <span className="text-[13px] text-muted">« Je compte l’XP de tout le monde. Personne ne compte la mienne. »</span>
          </div>
        </div>
        <StatusPill status={status} />
      </div>

      {tiles.length > 0 ? (
        <dl
          className={cn(
            "m-0 grid gap-3.5 max-[560px]:grid-cols-1",
            tiles.length >= 3 ? "grid-cols-3 max-[1000px]:grid-cols-2" : "grid-cols-2",
          )}
          data-testid="hermes-tiles"
        >
          {tiles.map(t => (
            <div key={t.label} className="grid content-start gap-1 rounded-2xl border border-line bg-[rgb(12_14_26/0.6)] px-[18px] py-4">
              <dt className="text-[13px] text-muted">{t.label}</dt>
              <dd
                className={cn(
                  "m-0 font-display leading-[1.1] font-bold tabular-nums",
                  t.compact ? "text-[22px]" : "text-[30px]",
                )}
              >
                {t.value}
              </dd>
              <dd className="m-0 text-xs text-muted">{t.note}</dd>
            </div>
          ))}
        </dl>
      ) : (
        <p className="m-0 text-sm text-muted">
          {status ? "Aucun relevé pour l’instant. Hermes prend ses marques." : "Tableau de bord indisponible : Hermes ne répond pas à l’appel."}
        </p>
      )}
    </>
  )
}
