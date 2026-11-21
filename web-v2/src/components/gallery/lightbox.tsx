"use client"

import Image from "next/image"
import { useEffect, useId, useRef, type KeyboardEvent, type MouseEvent } from "react"
import { Avatar } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import type { GalleryItem } from "@/lib/api/types"
import { formatDate } from "@/lib/format"
import { captionOf, clipEmbedUrl, galleryImageSrc, kindLabel, parseClip } from "@/lib/gallery"

type LightboxProps = {
  item: GalleryItem
  /** Appelé une fois le dialogue fermé (Échap, clic hors cadre, bouton) : le parent rend le focus. */
  onClose: () => void
}

function Visual({ item }: { item: GalleryItem }) {
  const image = galleryImageSrc(item)
  if (image) {
    return <Image src={image} alt={captionOf(item)} fill sizes="(max-width: 948px) 100vw, 900px" unoptimized className="object-contain" />
  }
  const clip = parseClip(item)
  if (clip) {
    return (
      <iframe
        src={clipEmbedUrl(clip, window.location.hostname)}
        title={`${captionOf(item)} (lecteur ${clip.label})`}
        className="absolute inset-0 size-full border-0"
        allow="autoplay; encrypted-media; fullscreen; picture-in-picture"
        referrerPolicy="strict-origin-when-cross-origin"
      />
    )
  }
  return (
    <p className="absolute inset-0 m-0 grid place-items-center px-6 text-center text-muted">
      Ce souvenir ne peut pas être affiché ici.
    </p>
  )
}

/**
 * Aperçu agrandi : `<dialog>` natif en modale (focus piégé, fond inerte). Échap, un clic sur la toile
 * de fond ou « Fermer » le ferment. Sans `showModal` (jsdom), le dialogue s'ouvre par l'attribut.
 */
export function Lightbox({ item, onClose }: LightboxProps) {
  const ref = useRef<HTMLDialogElement>(null)
  const titleId = useId()
  const clip = parseClip(item)
  const date = item.created_at ? formatDate(item.created_at) : null

  useEffect(() => {
    const dialog = ref.current
    if (!dialog || dialog.open) return
    if (typeof dialog.showModal === "function") dialog.showModal()
    else dialog.setAttribute("open", "")
    // `showModal` donne le focus au premier élément focusable, l'iframe du lecteur : Échap tapé dedans
    // (document d'une autre origine) n'atteindrait jamais le dialogue. Le focus va donc à « Fermer ».
    dialog.querySelector<HTMLElement>("[data-lightbox-close]")?.focus()
  }, [])

  // Le navigateur émet `close` après `dialog.close()` ; sans API native, on prévient le parent soi-même.
  const requestClose = () => {
    const dialog = ref.current
    if (dialog?.open && typeof dialog.close === "function") dialog.close()
    else onClose()
  }

  const onKeyDown = (e: KeyboardEvent<HTMLDialogElement>) => {
    if (e.key !== "Escape") return
    e.preventDefault() // une seule fermeture, la nôtre, plutôt que l'annulation native
    requestClose()
  }

  // Le cadre remplit le dialogue : un clic dont la cible est le dialogue lui-même vient de la toile de fond.
  const onClick = (e: MouseEvent<HTMLDialogElement>) => {
    if (e.target === e.currentTarget) requestClose()
  }

  return (
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      onKeyDown={onKeyDown}
      onClick={onClick}
      onClose={onClose}
      className="m-auto w-[min(900px,calc(100%-32px))] max-w-none overflow-visible bg-transparent p-0 text-fg backdrop:bg-[rgb(6_7_14/0.82)] backdrop:backdrop-blur-[8px]"
    >
      <div className="overflow-hidden rounded-[22px] border border-white/12 bg-panel shadow-[0_30px_80px_rgb(0_0_0/0.6)]">
        <div className="relative h-[min(60vh,480px)] bg-black/40">
          <Visual item={item} />
        </div>
        <div className="flex items-center justify-between gap-4 px-[22px] py-[18px] max-[560px]:flex-wrap">
          <div className="flex min-w-0 items-center gap-3">
            <Avatar name={item.author.name} src={item.author.avatar} size={40} />
            <div className="min-w-0">
              <b id={titleId} className="block truncate font-display text-xl">
                {captionOf(item)}
              </b>
              <span className="text-sm text-muted">
                <span className="text-msg">{item.author.name}</span>
                {` · ${kindLabel(item)}`}
                {date && ` · ${date}`}
              </span>
            </div>
          </div>
          <div className="flex flex-none items-center gap-2">
            {clip && (
              <Button href={clip.url} variant="ghost" className="px-4 py-2.5">
                Voir sur {clip.label}
              </Button>
            )}
            <Button variant="ghost" onClick={requestClose} data-lightbox-close className="px-4 py-2.5">
              Fermer
            </Button>
          </div>
        </div>
      </div>
    </dialog>
  )
}
