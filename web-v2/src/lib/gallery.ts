import type { GalleryItem } from "@/lib/api/types"

export type ClipProvider = "youtube" | "twitch" | "medal"

const PROVIDER_LABELS: Record<ClipProvider, string> = { youtube: "YouTube", twitch: "Twitch", medal: "Medal" }

export type Clip = {
  provider: ClipProvider
  label: string
  /** URL canonique, revalidée : sûre comme lien sortant. */
  url: string
  /** Identifiant tiré de l'URL (vidéo YouTube, clip Twitch) ou chemin Medal. */
  ref: string
}

/*
 * Formes canoniques produites par le bot (bot/utils/gallery.py, canonical_clip) et rien d'autre :
 * la chaîne entière doit correspondre, l'hôte et le schéma sont fixés par l'expression.
 */
const CANONICAL: Record<ClipProvider, RegExp> = {
  youtube: /^https:\/\/www\.youtube\.com\/watch\?v=([A-Za-z0-9_-]{11})$/,
  twitch: /^https:\/\/clips\.twitch\.tv\/([A-Za-z0-9_-]+)$/,
  medal: /^https:\/\/medal\.tv\/((?:[A-Za-z0-9_-]+\/)*[A-Za-z0-9_-]+)$/,
}

/** Clip reconnu (fournisseur annoncé et URL canonique concordants), sinon `null`. */
export function parseClip(item: Pick<GalleryItem, "kind" | "url" | "provider">): Clip | null {
  if (item.kind !== "clip" || !item.url || !item.provider) return null
  const provider = item.provider.toLowerCase()
  if (!(provider in CANONICAL)) return null
  const p = provider as ClipProvider
  const match = CANONICAL[p].exec(item.url)
  return match ? { provider: p, label: PROVIDER_LABELS[p], url: item.url, ref: match[1] } : null
}

/**
 * Adresse du lecteur intégré, construite à partir de l'identifiant validé (jamais de l'URL reçue).
 * Twitch exige le domaine qui intègre (`parent`). Chaque hôte doit figurer dans `frame-src`
 * (next.config.ts).
 */
export function clipEmbedUrl(clip: Clip, host: string): string {
  switch (clip.provider) {
    case "youtube":
      return `https://www.youtube-nocookie.com/embed/${clip.ref}`
    case "twitch":
      return `https://clips.twitch.tv/embed?clip=${clip.ref}&parent=${encodeURIComponent(host)}`
    case "medal":
      return `https://medal.tv/${clip.ref}`
  }
}

/** Miniature servie par le fournisseur quand elle est connue sans appel d'API (YouTube). */
export function clipThumbnail(clip: Clip): string | null {
  return clip.provider === "youtube" ? `https://i.ytimg.com/vi/${clip.ref}/hqdefault.jpg` : null
}

/** Image de la galerie : uniquement sous `/media/` (volume partagé, servi par le rewrite). */
export function galleryImageSrc(item: Pick<GalleryItem, "kind" | "url">): string | null {
  return item.kind === "image" && item.url?.startsWith("/media/") ? item.url : null
}

/** « Capture », « Clip YouTube », ou « Clip » quand le fournisseur est inconnu. */
export function kindLabel(item: Pick<GalleryItem, "kind" | "url" | "provider">): string {
  if (item.kind === "image") return "Capture"
  const clip = parseClip(item)
  return clip ? `Clip ${clip.label}` : "Clip"
}

export const captionOf = (item: Pick<GalleryItem, "caption">) => item.caption?.trim() || "Souvenir sans légende"
