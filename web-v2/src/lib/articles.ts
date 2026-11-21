import type { Article, SessionUser } from "@/lib/api/types"

/**
 * Image affichable d'un article (couverture ou image Markdown) : le volume média (`/media/<fichier>`,
 * relayé par le rewrite de Next) ou le CDN Discord. Les anciennes images insérées par l'ancien site portent
 * une URL absolue vers web-api (`https://…/media/<fichier>`) : on les ramène au chemin local.
 * Tout autre hôte serait de toute façon bloqué par la CSP `img-src` : mieux vaut ne rien afficher.
 */
export function safeImageSrc(raw: string | null | undefined): string | null {
  const text = raw?.trim()
  if (!text) return null
  if (/^\/media\/[\w.-]+$/.test(text)) return text
  let url: URL
  try {
    url = new URL(text)
  } catch {
    return null
  }
  if (url.protocol !== "https:" && url.protocol !== "http:") return null
  const media = url.pathname.match(/\/media\/([\w.-]+)$/)
  if (media && media[1] !== "." && media[1] !== "..") return `/media/${media[1]}`
  if (url.protocol === "https:" && url.hostname === "cdn.discordapp.com") return url.toString()
  return null
}

/** Résumé en texte brut (balises Markdown retirées) pour la méta-description. */
export function excerpt(content: string, max = 160): string {
  return content
    .slice(0, max)
    .replace(/[#*`_>\[\]\n]/g, " ")
    .replace(/\s+/g, " ")
    .trim()
}

/** Création : rédacteurs et administrateurs. */
export const canWrite = (me: SessionUser | null): boolean => !!me && (me.is_redacteur || me.is_admin)

/** Modification et suppression : l'auteur ou un administrateur (même règle que `PUT/DELETE /articles/{id}`). */
export const canEdit = (me: SessionUser | null, article: Pick<Article, "author_id">): boolean =>
  !!me && (me.is_admin || String(me.user_id) === String(article.author_id))

/** Couleur de tag venue de la base : seule une couleur hexadécimale est injectée dans un style. */
export function tagColor(color: string | null | undefined): string {
  return color && /^#[0-9a-fA-F]{6}$/.test(color) ? color : "#9A97B8"
}
