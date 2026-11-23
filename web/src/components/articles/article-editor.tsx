"use client"

import Image from "next/image"
import { useRouter } from "next/navigation"
import { useRef, useState } from "react"
import { Markdown } from "@/components/articles/markdown"
import { api } from "@/lib/api/client"
import { seg } from "@/lib/api/query"
import type { Article, Tag } from "@/lib/api/types"
import { safeImageSrc, tagColor } from "@/lib/articles"
import { cn } from "@/lib/cn"

type Props = {
  /** Absent : création. */
  article?: Article
  availableTags: Tag[]
}

const FIELD =
  "w-full rounded-xl border border-line bg-[rgb(19_22_42/0.9)] px-4 py-3 text-fg placeholder:text-muted focus:border-violet/60 focus:outline-none"

/**
 * Éditeur d'article : Markdown en `textarea` avec aperçu rendu par le même composant que la page publique
 * (GFM, code coloré, HTML brut jamais interprété).
 */
export function ArticleEditor({ article, availableTags }: Props) {
  const router = useRouter()
  const isEdit = !!article
  const fileInput = useRef<HTMLInputElement>(null)

  const [title, setTitle] = useState(article?.title ?? "")
  const [content, setContent] = useState(article?.content ?? "")
  const [coverUrl, setCoverUrl] = useState(article?.cover_image_url ?? "")
  const [selected, setSelected] = useState<number[]>(article?.tags.map(t => t.id) ?? [])
  const [preview, setPreview] = useState(false)
  const [saving, setSaving] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState("")

  const cover = safeImageSrc(coverUrl)

  const toggleTag = (id: number) =>
    setSelected(prev => (prev.includes(id) ? prev.filter(t => t !== id) : [...prev, id]))

  async function upload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    e.target.value = ""
    if (!file) return
    setUploading(true)
    setError("")
    try {
      const { url } = await api.media.upload(file)
      // Le volume média est servi sur le même domaine (`/media/…`) : la CSP `img-src 'self'` s'applique.
      const alt = file.name.replace(/[[\]]/g, "")
      setContent(prev => `${prev}${prev && !prev.endsWith("\n") ? "\n" : ""}![${alt}](${url})\n`)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Envoi impossible")
    } finally {
      setUploading(false)
    }
  }

  async function save(published: boolean) {
    if (!title.trim() || !content.trim()) {
      setError("Titre et contenu requis")
      return
    }
    setSaving(true)
    setError("")
    try {
      const payload = {
        title: title.trim(),
        content,
        // Mise à jour : `null` ne retire pas la couverture (web-api ignore les champs nuls), la chaîne vide, si.
        cover_image_url: coverUrl.trim() || (isEdit ? "" : undefined),
        published,
        tag_ids: selected,
      }
      const saved = article ? await api.articles.update(article.id, payload) : await api.articles.create(payload)
      router.push(`/articles/${seg(saved.slug)}`)
      router.refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Enregistrement impossible")
      setSaving(false)
    }
  }

  return (
    <div className="space-y-5">
      <input
        value={title}
        onChange={e => setTitle(e.target.value)}
        placeholder="Titre de l'article"
        aria-label="Titre de l'article"
        maxLength={200}
        className={cn(FIELD, "font-display text-xl font-bold")}
      />

      <div>
        <input
          value={coverUrl}
          onChange={e => setCoverUrl(e.target.value)}
          placeholder="Image de couverture (optionnel) : /media/… ou lien Discord"
          aria-label="Image de couverture"
          className={cn(FIELD, "py-2 text-sm")}
        />
        {coverUrl.trim() && !cover && (
          <p className="mt-2 text-xs text-gold" role="status">
            Seules les images du site (/media/…) et du CDN Discord s’affichent : celle-ci serait bloquée.
          </p>
        )}
        {cover && (
          <div className="relative mt-3 h-48 overflow-hidden rounded-xl">
            <Image src={cover} alt="Aperçu de la couverture" fill unoptimized className="object-cover" />
          </div>
        )}
      </div>

      <fieldset>
        <legend className="mb-2 text-sm font-semibold">Tags</legend>
        {availableTags.length === 0 ? (
          <p className="text-sm text-muted">Aucun tag disponible. Crée-les depuis la page Articles.</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {availableTags.map(tag => {
              const on = selected.includes(tag.id)
              const color = tagColor(tag.color)
              return (
                <button
                  key={tag.id}
                  type="button"
                  onClick={() => toggleTag(tag.id)}
                  aria-pressed={on}
                  className={cn("rounded-full border px-3 py-1 text-sm font-semibold", !on && "border-line text-muted")}
                  style={on ? { borderColor: color, color, backgroundColor: `${color}33` } : undefined}
                >
                  {tag.name}
                </button>
              )
            })}
          </div>
        )}
      </fieldset>

      <div>
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <div role="group" aria-label="Mode" className="flex gap-1">
            {[
              { key: false, label: "Écrire" },
              { key: true, label: "Aperçu" },
            ].map(m => (
              <button
                key={m.label}
                type="button"
                aria-pressed={preview === m.key}
                onClick={() => setPreview(m.key)}
                className={cn(
                  "rounded-lg border px-3 py-1.5 text-sm font-semibold",
                  preview === m.key ? "border-violet bg-violet/10 text-violet" : "border-line text-muted hover:text-fg",
                )}
              >
                {m.label}
              </button>
            ))}
          </div>
          <button
            type="button"
            onClick={() => fileInput.current?.click()}
            disabled={uploading}
            className="rounded-lg border border-line px-3 py-1.5 text-sm text-muted hover:border-violet/40 hover:text-fg disabled:opacity-50"
          >
            {uploading ? "Envoi…" : "Insérer une image"}
          </button>
          <input
            ref={fileInput}
            type="file"
            accept="image/jpeg,image/png,image/gif,image/webp"
            onChange={upload}
            className="hidden"
            aria-label="Fichier image à insérer"
          />
        </div>
        {preview ? (
          <div className="min-h-[520px] rounded-xl border border-line bg-[rgb(19_22_42/0.6)] p-6" aria-label="Aperçu de l'article">
            {content.trim() ? <Markdown>{content}</Markdown> : <p className="text-muted">Rien à prévisualiser.</p>}
          </div>
        ) : (
          <textarea
            value={content}
            onChange={e => setContent(e.target.value)}
            placeholder="Contenu en Markdown…"
            aria-label="Contenu de l'article (Markdown)"
            className={cn(FIELD, "min-h-[520px] resize-y font-mono text-sm leading-relaxed")}
          />
        )}
      </div>

      {error && (
        <p role="alert" className="text-sm text-[#FF8F8F]">
          {error}
        </p>
      )}

      <div className="flex flex-wrap gap-3 pt-2">
        <button
          type="button"
          onClick={() => save(true)}
          disabled={saving}
          className="rounded-xl bg-violet-deep px-6 py-2.5 text-sm font-bold text-white disabled:opacity-50"
        >
          {saving ? "…" : isEdit ? "Mettre à jour et publier" : "Publier"}
        </button>
        <button
          type="button"
          onClick={() => save(false)}
          disabled={saving}
          className="rounded-xl border border-line bg-white/6 px-6 py-2.5 text-sm font-semibold disabled:opacity-50"
        >
          {saving ? "…" : isEdit ? "Sauvegarder en brouillon" : "Brouillon"}
        </button>
        <button type="button" onClick={() => router.back()} className="px-4 py-2 text-sm text-muted hover:text-fg">
          Annuler
        </button>
      </div>
    </div>
  )
}
