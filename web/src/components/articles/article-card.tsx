import Image from "next/image"
import Link from "next/link"
import { Chip } from "@/components/ui/chip"
import { seg } from "@/lib/api/query"
import type { Article } from "@/lib/api/types"
import { safeImageSrc, tagColor } from "@/lib/articles"
import { formatDate } from "@/lib/format"

export function TagChips({ tags }: { tags: Article["tags"] }) {
  return tags.map(tag => (
    <Chip key={tag.id} color={tagColor(tag.color)}>
      {tag.name}
    </Chip>
  ))
}

/** Carte d'article de la liste ; `draft` : brouillon de l'auteur, avec accès direct à l'éditeur. */
export function ArticleCard({ article, draft = false }: { article: Article; draft?: boolean }) {
  const cover = safeImageSrc(article.cover_image_url)
  return (
    <article className="group flex flex-col overflow-hidden rounded-[20px] border border-line bg-[rgb(19_22_42/0.92)] shadow-[0_16px_30px_rgb(0_0_0/0.35)] transition-colors hover:border-violet/35">
      {cover && (
        <div className="relative h-48 overflow-hidden">
          <Image
            src={cover}
            alt=""
            fill
            unoptimized
            sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 33vw"
            className="object-cover transition-transform duration-500 group-hover:scale-105"
          />
        </div>
      )}
      <div className="flex flex-1 flex-col p-5">
        {(draft || article.tags.length > 0) && (
          <div className="mb-3 flex flex-wrap gap-1.5">
            {draft && <Chip color="var(--color-gold)">Brouillon</Chip>}
            <TagChips tags={article.tags} />
          </div>
        )}
        <h3 className="mb-2 line-clamp-2 font-display text-lg font-bold">
          <Link href={`/articles/${seg(article.slug)}`} prefetch={false} className="hover:text-violet">
            {article.title}
          </Link>
        </h3>
        <p className="mb-4 text-sm text-muted">
          Par <span className="font-medium text-fg">{article.author?.username ?? "—"}</span> ·{" "}
          {formatDate(article.created_at)}
        </p>
        <div className="mt-auto flex items-center justify-between">
          <Link
            href={`/articles/${seg(article.slug)}`}
            prefetch={false}
            className="text-sm font-semibold text-cyan hover:underline"
          >
            Lire la suite →
          </Link>
          {draft && (
            <Link
              href={`/editeur/${seg(article.id)}`}
              prefetch={false}
              className="rounded-md border border-line px-2.5 py-1 text-xs text-muted hover:border-violet/40 hover:text-fg"
            >
              Modifier
            </Link>
          )}
        </div>
      </div>
    </article>
  )
}
