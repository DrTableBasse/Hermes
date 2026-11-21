"use client"

import { useState } from "react"
import { Chip } from "@/components/ui/chip"
import { api } from "@/lib/api/client"
import type { Tag } from "@/lib/api/types"
import { tagColor } from "@/lib/articles"

const PRESET_COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899", "#06b6d4", "#84cc16"]

const FIELD =
  "rounded-lg border border-line bg-bg px-3 py-1.5 text-sm text-fg placeholder:text-muted focus:border-violet/60 focus:outline-none"

const message = (e: unknown) => (e instanceof Error ? e.message : "Erreur inattendue")

/** Gestion des tags (rédacteurs) : création avec couleur, suppression. */
export function TagManager({ initialTags }: { initialTags: Tag[] }) {
  const [open, setOpen] = useState(false)
  const [tags, setTags] = useState(initialTags)
  const [name, setName] = useState("")
  const [color, setColor] = useState(PRESET_COLORS[0])
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState("")

  async function create() {
    if (!name.trim() || saving) return
    setSaving(true)
    setError("")
    try {
      const tag = await api.tags.create({ name: name.trim(), color })
      setTags(prev => [...prev, tag].sort((a, b) => a.name.localeCompare(b.name, "fr")))
      setName("")
    } catch (e) {
      setError(message(e))
    } finally {
      setSaving(false)
    }
  }

  async function remove(tag: Tag) {
    if (!window.confirm("Supprimer ce tag ? Il sera retiré de tous les articles.")) return
    setError("")
    try {
      await api.tags.delete(tag.id)
      setTags(prev => prev.filter(t => t.id !== tag.id))
    } catch (e) {
      setError(message(e))
    }
  }

  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        aria-expanded={open}
        className="rounded-lg border border-line px-3 py-1.5 text-xs text-muted hover:border-violet/40 hover:text-fg"
      >
        {open ? "Fermer" : "Gérer les tags"}
      </button>
      {open && (
        <div className="mt-4 space-y-4 rounded-2xl border border-line bg-[rgb(19_22_42/0.92)] p-5">
          <h3 className="text-sm font-semibold">Gestion des tags</h3>
          <div className="flex flex-wrap items-end gap-3">
            <label className="block text-xs text-muted">
              Nom
              <input
                value={name}
                onChange={e => setName(e.target.value)}
                onKeyDown={e => e.key === "Enter" && create()}
                placeholder="Nouveau tag…"
                maxLength={50}
                className={`${FIELD} mt-1 block w-40`}
              />
            </label>
            <fieldset className="text-xs text-muted">
              <legend className="mb-1">Couleur</legend>
              <div className="flex items-center gap-1.5">
                {PRESET_COLORS.map(c => (
                  <button
                    key={c}
                    type="button"
                    onClick={() => setColor(c)}
                    aria-label={`Couleur ${c}`}
                    aria-pressed={color === c}
                    className={`size-6 rounded-full border-2 ${color === c ? "scale-110 border-white" : "border-transparent"}`}
                    style={{ backgroundColor: c }}
                  />
                ))}
                <input
                  type="color"
                  value={color}
                  onChange={e => setColor(e.target.value)}
                  aria-label="Couleur personnalisée"
                  className="size-6 cursor-pointer rounded border-0 bg-transparent"
                />
              </div>
            </fieldset>
            <button
              type="button"
              onClick={create}
              disabled={saving || !name.trim()}
              className="rounded-lg bg-violet-deep px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-50"
            >
              {saving ? "…" : "Créer"}
            </button>
          </div>
          {error && (
            <p role="alert" className="text-xs text-[#FF8F8F]">
              {error}
            </p>
          )}
          {tags.length === 0 ? (
            <p className="text-sm text-muted">Aucun tag créé.</p>
          ) : (
            <ul className="flex flex-wrap gap-2">
              {tags.map(tag => (
                <li key={tag.id}>
                  <Chip color={tagColor(tag.color)}>
                    {tag.name}
                    <button
                      type="button"
                      onClick={() => remove(tag)}
                      aria-label={`Supprimer le tag ${tag.name}`}
                      className="ml-1 leading-none hover:opacity-70"
                    >
                      ✕
                    </button>
                  </Chip>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
