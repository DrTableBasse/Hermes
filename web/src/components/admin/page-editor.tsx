"use client"

import { useId, useState, type FormEvent } from "react"
import { Markdown } from "@/components/articles/markdown"
import { Button } from "@/components/ui/button"
import { Panel } from "@/components/ui/panel"
import { api } from "@/lib/api/client"
import type { SitePage } from "@/lib/api/types"
import { cn } from "@/lib/cn"
import { formatNumber } from "@/lib/format"
import { adminErrorText, FIELD, LABEL, type Feedback } from "./form"

/** Limites de `PUT /admin/pages/{slug}`. */
export const BODY_MAX = 50_000
const TITLE_MAX = 200

/**
 * Page Markdown (règlement, mentions légales) avec aperçu : même rendu que les articles, le HTML brut
 * s'affiche comme du texte.
 */
export function PageEditor({ page }: { page: SitePage }) {
  const ids = useId()
  const [title, setTitle] = useState(page.title)
  const [body, setBody] = useState(page.body_md)
  const [preview, setPreview] = useState(false)
  const [busy, setBusy] = useState(false)
  const [feedback, setFeedback] = useState<Feedback>(null)

  const error = !title.trim()
    ? "Titre requis."
    : [...title.trim()].length > TITLE_MAX
      ? `Titre : ${TITLE_MAX} caractères maximum.`
      : body.length > BODY_MAX
        ? `Contenu : ${formatNumber(BODY_MAX)} caractères maximum.`
        : null

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (error || busy) return
    setBusy(true)
    setFeedback(null)
    try {
      await api.admin.updatePage(page.slug, { title: title.trim(), body_md: body })
      setFeedback({ kind: "ok", text: "Enregistré. La page publique se met à jour sous cinq minutes." })
    } catch (err) {
      setFeedback({ kind: "error", text: adminErrorText(err) })
    } finally {
      setBusy(false)
    }
  }

  return (
    <Panel as="section" aria-labelledby={`${ids}-heading`} className="grid gap-4">
      <h2 id={`${ids}-heading`} className="m-0 font-display text-xl font-extrabold">
        {page.title || page.slug}
      </h2>
      <form onSubmit={submit} noValidate className="grid gap-4">
        <div className="grid gap-1.5">
          <label htmlFor={`${ids}-title`} className={LABEL}>
            Titre
          </label>
          <input id={`${ids}-title`} value={title} onChange={e => setTitle(e.target.value)} className={FIELD} />
        </div>
        <div role="group" aria-label="Mode d’édition" className="flex gap-1.5">
          {[false, true].map(p => (
            <button
              key={String(p)}
              type="button"
              aria-pressed={preview === p}
              onClick={() => setPreview(p)}
              className={cn(
                "rounded-full border px-3 py-1 text-sm font-semibold",
                preview === p ? "border-violet bg-violet/10 text-violet" : "border-line text-muted hover:text-fg",
              )}
            >
              {p ? "Aperçu" : "Markdown"}
            </button>
          ))}
        </div>
        {preview ? (
          <div className="min-h-48 rounded-xl border border-line px-5 py-4" aria-label="Aperçu">
            {body.trim() ? <Markdown>{body}</Markdown> : <p className="m-0 text-muted">Page vide.</p>}
          </div>
        ) : (
          <div className="grid gap-1.5">
            <label htmlFor={`${ids}-body`} className={LABEL}>
              Contenu (Markdown)
            </label>
            <textarea
              id={`${ids}-body`}
              rows={16}
              value={body}
              onChange={e => setBody(e.target.value)}
              aria-invalid={body.length > BODY_MAX}
              className={cn(FIELD, "font-mono text-sm")}
            />
            <span className={cn("text-xs tabular-nums", body.length > BODY_MAX ? "text-orange" : "text-muted")}>
              {formatNumber(body.length)} / {formatNumber(BODY_MAX)}
            </span>
          </div>
        )}
        {error && <p className="m-0 text-sm text-orange">{error}</p>}
        <div className="flex flex-wrap items-center gap-3">
          <Button type="submit" size="sm" disabled={busy || error !== null}>
            {busy ? "…" : "Enregistrer"}
          </Button>
          {feedback && (
            <p role={feedback.kind === "error" ? "alert" : "status"} className={cn("m-0 text-sm", feedback.kind === "error" ? "text-orange" : "text-green")}>
              {feedback.text}
            </p>
          )}
        </div>
      </form>
    </Panel>
  )
}
