import { Button } from "@/components/ui/button"
import { LiveDot } from "@/components/ui/section-heading"
import type { LiveState } from "@/lib/api/types"
import { formatClock, formatNumber } from "@/lib/format"

type FinalCtaProps = {
  /** `null` : pas de pastille de présence. */
  live: LiveState | null
  /** `invite_url` des réglages publics ; `null` : bouton désactivé avec un texte explicite. */
  inviteUrl: string | null
}

/** Appel final « Rejoins les Généraux Saucisses ». Réservé à l'accueil (vérifié par test). */
export function FinalCta({ live, inviteUrl }: FinalCtaProps) {
  return (
    <section className="relative pt-10 pb-24" aria-labelledby="final-title">
      <div className="relative mx-auto max-w-[1440px] px-6 min-[1100px]:px-20">
        <div className="grid justify-items-center gap-4 rounded-[30px] border border-violet/35 bg-[radial-gradient(600px_300px_at_50%_0%,rgb(155_107_255/0.35),transparent_70%),rgb(19_22_42/0.75)] px-6 py-16 text-center">
          {live &&
            (live.stale ? (
              <LiveDot color="var(--color-orange)">
                Dernier relevé à {formatClock(live.updated_at)}, {formatNumber(live.online)} Généraux en ligne
              </LiveDot>
            ) : (
              <LiveDot>{formatNumber(live.online)} Généraux en ligne</LiveDot>
            ))}
          <h2
            id="final-title"
            className="m-0 font-display text-[clamp(38px,4.6vw,56px)] leading-none font-extrabold tracking-[-0.03em] text-balance"
          >
            Rejoins les Généraux Saucisses
          </h2>
          <p className="m-0 max-w-[62ch] text-lg text-muted">
            La caserne t’attend. Présente-toi en arrivant, choisis tes jeux, et la première tournée d’XP est pour nous.
          </p>
          {inviteUrl ? (
            <Button href={inviteUrl} size="lg" sausage className="mt-2 px-[30px] py-[18px] text-[17px]">
              Rejoindre le Discord
            </Button>
          ) : (
            <Button size="lg" disabled className="mt-2">
              Invitation indisponible pour le moment
            </Button>
          )}
        </div>
      </div>
    </section>
  )
}
