import type { CSSProperties } from "react"
import { TileVisual } from "@/components/gallery/gallery-strips"
import { Button } from "@/components/ui/button"
import { SectionHeading } from "@/components/ui/section-heading"
import type { GalleryItem, GalleryResponse } from "@/lib/api/types"
import { cn } from "@/lib/cn"
import { captionOf, kindLabel, parseClip } from "@/lib/gallery"

/** Fonds des tuiles sans image (clips) : teintes de la maquette, attribuées par position. */
const TINTS = ["#9B6BFF", "#B3202D", "#5DAA3A"]

function Moment({ item, index }: { item: GalleryItem; index: number }) {
  const tint = TINTS[index % TINTS.length]
  const isClip = item.kind === "clip"
  // Un clip reconnu (URL canonique, `parseClip`) s'ouvre chez son hébergeur ; le reste renvoie aux archives.
  const clip = parseClip(item)
  const href = clip ? clip.url : "/galerie"
  const external = clip !== null
  const caption = captionOf(item)

  return (
    <li className="min-w-0">
      <a
        href={href}
        {...(external ? { target: "_blank", rel: "noopener noreferrer" } : {})}
        className="group relative block h-[300px] overflow-hidden rounded-2xl border border-line transition-[transform,box-shadow] duration-250 hover:scale-[1.03] hover:shadow-[0_18px_40px_rgb(0_0_0/0.5)] max-[900px]:h-[220px]"
        style={{ "--g1": tint, "--g2": `color-mix(in srgb, ${tint} 18%, #0C0E1A)` } as CSSProperties}
        data-kind={item.kind}
      >
        <span className="absolute inset-0 bg-linear-to-b from-(--g1) to-(--g2)" aria-hidden="true">
          {/* Même rendu que /galerie : capture via l'optimiseur Next, jamais l'original. */}
          <TileVisual item={item} sizes="(max-width: 900px) 100vw, 40vw" />
          <span className="absolute inset-x-0 top-[45%] bottom-0 bg-linear-to-b from-transparent to-[rgb(12_14_26/0.95)]" />
        </span>
        <span className="absolute top-3 right-3 z-2 rounded-full bg-black/45 px-[9px] py-[3px] text-[11px] font-bold text-white">
          {kindLabel(item)}
        </span>
        {isClip && (
          <span
            className="absolute top-[42%] left-1/2 z-2 -mt-[23px] -ml-[23px] grid size-[46px] place-items-center rounded-full border border-white/40 bg-white/18 backdrop-blur-[6px]"
            aria-hidden="true"
          >
            <svg width="16" height="16" viewBox="0 0 16 16">
              <path d="M4 2l10 6-10 6z" fill="#fff" />
            </svg>
          </span>
        )}
        <span className="absolute inset-x-3.5 bottom-3 z-2 grid gap-0.5">
          <b className={cn("truncate font-display text-[15px] text-white", index === 0 && "text-xl")}>{caption}</b>
          <span className="text-xs text-msg">{item.author.name}</span>
        </span>
      </a>
    </li>
  )
}

/** Les 3 moments de la semaine ; `null` (API muette) → section masquée, liste vide → invitation à poster. */
export function GalleryPreview({ data }: { data: GalleryResponse | null }) {
  if (!data) return null
  const items = data.items.slice(0, 3)

  return (
    <section className="relative pt-10 pb-24" aria-labelledby="moments-title">
      <div className="relative mx-auto max-w-[1440px] px-6 min-[1100px]:px-20">
        <SectionHeading
          id="moments-title"
          title="Les moments de la semaine"
          sub="Les trois derniers souvenirs de la commu, validés par le staff et rangés dans les archives."
          action={
            <Button href="/galerie" variant="ghost" className="px-5 py-3 text-[15px]">
              Toute la galerie
            </Button>
          }
        />
        {items.length > 0 ? (
          <ul
            className="m-0 mt-8 grid list-none grid-cols-[1.4fr_1fr_1fr] gap-5 p-0 max-[900px]:grid-cols-[minmax(0,1fr)]"
            aria-label="Moments de la semaine"
          >
            {items.map((item, i) => (
              <Moment key={item.id} item={item} index={i} />
            ))}
          </ul>
        ) : (
          <div className="mt-8 grid justify-items-start gap-3 rounded-3xl border border-dashed border-white/12 bg-[rgb(19_22_42/0.6)] px-8 py-10 max-[640px]:px-6">
            <p className="m-0 font-display text-[clamp(24px,2.6vw,32px)] font-bold">Les archives attendent leur premier souvenir.</p>
            <p className="m-0 max-w-[60ch] text-muted">
              Poste ta capture ou ton clip dans <code className="font-mono text-cyan">#galerie</code>, le staff la valide
              d’une réaction, Hermes l’envoie ici.
            </p>
          </div>
        )}
      </div>
    </section>
  )
}
