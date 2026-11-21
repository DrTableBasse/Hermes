"use client"

import Image from "next/image"
import { useRef, useState, type CSSProperties } from "react"
import { Lightbox } from "@/components/gallery/lightbox"
import { Marquee } from "@/components/ui/marquee"
import type { GalleryItem } from "@/lib/api/types"
import { captionOf, clipThumbnail, galleryImageSrc, kindLabel, parseClip } from "@/lib/gallery"

/** Teintes et largeurs des vignettes de la maquette, attribuées par position. */
const TINTS = ["#F99E1A", "#B3202D", "#9B6BFF", "#5DAA3A", "#0AC8B9", "#3FA9C9", "#FF8A3D", "#7A8A3A"]
const WIDTHS = [320, 380, 300, 340, 360, 300]

/** En dessous, une bande ne couvre pas un grand écran : ses vignettes sont répétées (cachées). */
const MIN_TILES = 6

type Slot = { item: GalleryItem; index: number; hidden: boolean }

/** Une vignette sur deux par bande, l'ordre de l'API (plus récent d'abord) préservé dans chacune. */
export function splitStrips(items: GalleryItem[]): GalleryItem[][] {
  const strips = [items.filter((_, i) => i % 2 === 0), items.filter((_, i) => i % 2 === 1)]
  return strips.filter(s => s.length > 0)
}

/** Vignettes d'une bande : chaque souvenir une fois, puis des répétitions cachées jusqu'à `MIN_TILES`. */
function fill(strip: GalleryItem[], offset: number): Slot[] {
  const slots = strip.map((item, i) => ({ item, index: offset + i * 2, hidden: false }))
  for (let i = 0; slots.length < MIN_TILES; i++) slots.push({ ...slots[i % strip.length], hidden: true })
  return slots
}

function TileVisual({ item }: { item: GalleryItem }) {
  const clip = parseClip(item)
  const src = galleryImageSrc(item) ?? (clip && clipThumbnail(clip))
  if (src) return <Image src={src} alt="" fill sizes="380px" unoptimized className="object-cover" />
  return (
    <span className="absolute inset-0 bg-[repeating-linear-gradient(135deg,rgb(255_255_255/0.05)_0_10px,transparent_10px_36px)]" />
  )
}

type TileProps = Slot & { onOpen: (item: GalleryItem, trigger: HTMLButtonElement) => void }

function Tile({ item, index, hidden, onOpen }: TileProps) {
  const tint = TINTS[index % TINTS.length]
  return (
    <button
      type="button"
      onClick={e => onOpen(item, e.currentTarget)}
      // Copies et répétitions : cliquables, mais ni annoncées ni atteintes au clavier.
      tabIndex={hidden ? -1 : undefined}
      aria-hidden={hidden || undefined}
      aria-haspopup="dialog"
      className="relative h-[200px] flex-none cursor-zoom-in overflow-hidden rounded-2xl border border-line p-0 text-left transition-[transform,box-shadow] duration-250 hover:scale-[1.03] hover:shadow-[0_18px_40px_rgb(0_0_0/0.5)]"
      style={{ width: WIDTHS[index % WIDTHS.length] }}
      data-kind={item.kind}
    >
      <span
        className="absolute inset-0 bg-linear-to-b from-(--g1) to-(--g2)"
        style={{ "--g1": tint, "--g2": `color-mix(in srgb, ${tint} 18%, #0C0E1A)` } as CSSProperties}
        aria-hidden="true"
      >
        <TileVisual item={item} />
        <span className="absolute inset-x-0 top-[45%] bottom-0 bg-linear-to-b from-transparent to-[rgb(12_14_26/0.95)]" />
      </span>
      <span className="absolute top-3 right-3 z-2 rounded-full bg-black/45 px-[9px] py-[3px] text-[11px] font-bold text-white">
        {kindLabel(item)}
      </span>
      {item.kind === "clip" && (
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
        <b className="truncate font-display text-[15px] text-white">{captionOf(item)}</b>
        <span className="truncate text-xs text-msg">{item.author.name}</span>
      </span>
    </button>
  )
}

/**
 * Deux bandeaux en sens inverse ; un clic ouvre l'aperçu agrandi, sa fermeture rend le focus à la
 * vignette cliquée.
 */
export function GalleryStrips({ items }: { items: GalleryItem[] }) {
  const [open, setOpen] = useState<GalleryItem | null>(null)
  const trigger = useRef<HTMLButtonElement | null>(null)

  const onOpen = (item: GalleryItem, button: HTMLButtonElement) => {
    trigger.current = button
    setOpen(item)
  }
  const onClose = () => {
    setOpen(null)
    trigger.current?.focus()
  }

  const strips = splitStrips(items)
  return (
    <>
      <div className="grid gap-[18px]" data-testid="gallery-strips">
        {strips.map((strip, s) => {
          const slots = fill(strip, s)
          const render = (copy: boolean) =>
            slots.map((slot, i) => <Tile key={`${slot.item.id}-${i}`} {...slot} hidden={copy || slot.hidden} onOpen={onOpen} />)
          return (
            <Marquee
              key={s}
              items={render(false)}
              copy={render(true)}
              reverse={s === 1}
              speed={s === 1 ? 55 : 45}
              aria-label={`Archives, bande ${s + 1} sur ${strips.length}`}
            />
          )
        })}
      </div>
      {open && <Lightbox key={open.id} item={open} onClose={onClose} />}
    </>
  )
}
