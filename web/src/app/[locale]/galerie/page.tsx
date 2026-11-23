import type { Metadata } from "next"
import { GalleryStrips } from "@/components/gallery/gallery-strips"
import { Button } from "@/components/ui/button"
import { SectionHeading } from "@/components/ui/section-heading"
import { getGallery, getPublicSettings } from "@/lib/api/server"

export const metadata: Metadata = {
  title: "Galerie · SaucisseLand",
  description: "Les archives de la caserne : captures et clips de la commu SaucisseLand, validés par le staff.",
}

const GALLERY_LIMIT = 40

const STEPS = [
  ["Poste", "ta capture ou ton clip (YouTube, Twitch, Medal) dans #galerie."],
  ["Le staff valide", "d’une réaction ✅ : rien ne part sans son accord."],
  ["Hermes l’archive", "ici, dans les bandeaux de la caserne."],
] as const

/** Vignettes fantômes du bandeau vide : teintes et largeurs de la maquette, purement décoratives. */
const GHOSTS = [
  ["#F99E1A", 320],
  ["#B3202D", 380],
  ["#9B6BFF", 300],
  ["#5DAA3A", 340],
  ["#0AC8B9", 360],
] as const

const Channel = () => <code className="font-mono text-cyan">#galerie</code>

function EmptyArchives({ inviteUrl }: { inviteUrl: string | null }) {
  return (
    <div
      className="relative mt-11 overflow-hidden rounded-[26px] border border-dashed border-white/12 bg-[rgb(19_22_42/0.6)]"
      data-testid="gallery-empty"
    >
      <div className="flex gap-5 overflow-hidden px-8 pt-8 opacity-35 max-[640px]:px-6" aria-hidden="true">
        {GHOSTS.map(([tint, width]) => (
          <span
            key={tint}
            className="h-[120px] flex-none rounded-2xl border border-dashed border-white/20"
            style={{ width, background: `linear-gradient(180deg, ${tint}55, transparent)` }}
          />
        ))}
      </div>
      <div className="grid justify-items-start gap-4 px-8 pt-6 pb-10 max-[640px]:px-6">
        <p className="m-0 font-display text-[clamp(26px,3vw,36px)] leading-tight font-bold text-balance">
          Poste tes meilleurs moments dans <Channel />
        </p>
        <p className="m-0 max-w-[60ch] text-muted">
          Les archives sont encore vides. Le premier souvenir validé ouvrira le défilé, avec ton pseudo dessous.
        </p>
        <ol className="m-0 mt-2 grid list-none grid-cols-3 gap-3.5 p-0 max-[860px]:grid-cols-[minmax(0,1fr)]">
          {STEPS.map(([title, text], i) => (
            <li key={title} className="flex gap-3 rounded-2xl border border-line bg-[rgb(12_14_26/0.6)] px-[18px] py-4">
              <span
                className="grid size-8 flex-none place-items-center rounded-full bg-violet-deep font-display font-bold text-white"
                aria-hidden="true"
              >
                {i + 1}
              </span>
              <p className="m-0 text-sm text-muted">
                <b className="text-fg">{title}</b> {text}
              </p>
            </li>
          ))}
        </ol>
        {inviteUrl && (
          <Button href={inviteUrl} className="mt-2 px-5 py-3 text-[15px]">
            Ouvrir le Discord
          </Button>
        )}
      </div>
    </div>
  )
}

export default async function GalleryPage() {
  // `null` : web-api muette ; on le dit plutôt que d'inviter à remplir une galerie peut-être pleine.
  const [gallery, settings] = await Promise.all([getGallery(GALLERY_LIMIT), getPublicSettings()])
  const items = gallery?.items ?? []

  return (
    <main className="relative pt-10 pb-24">
      <div className="pointer-events-none absolute inset-0 overflow-x-clip" aria-hidden="true">
        <div className="halo" style={{ right: "8%", top: 160, width: 680, height: 480, background: "rgb(155 107 255 / 0.12)" }} />
      </div>
      <div className="relative mx-auto max-w-[1440px] px-6 min-[1100px]:px-20">
        <SectionHeading
          as="h1"
          title="Les archives de la caserne"
          sub={
            items.length > 0
              ? "Captures, clips et souvenirs d’events, choisis par la commu. Passe la souris pour arrêter le défilé, clique pour agrandir."
              : "Captures, clips et souvenirs d’events, choisis par la commu et validés par le staff."
          }
        />
        {!gallery && (
          <p className="mt-11 rounded-2xl border border-line bg-[rgb(19_22_42/0.6)] px-6 py-5 text-muted" role="status">
            Les archives sont injoignables pour l’instant. Reviens dans un moment, les souvenirs ne bougent pas.
          </p>
        )}
        {gallery && items.length === 0 && <EmptyArchives inviteUrl={settings?.invite_url ?? null} />}
      </div>

      {items.length > 0 && (
        <>
          <div className="relative mt-11">
            <GalleryStrips items={items} />
          </div>
          <div className="relative mx-auto max-w-[1440px] px-6 min-[1100px]:px-20">
            <p className="mt-5 mb-0 text-sm text-muted">
              Poste ta capture dans <Channel />, le staff la valide d’une réaction, Hermes l’envoie ici.
            </p>
          </div>
        </>
      )}
    </main>
  )
}
