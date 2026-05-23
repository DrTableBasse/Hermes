'use client'

import { useState } from 'react'
import type { Tag } from '@/lib/api'
import { actionCreateTag, actionDeleteTag } from './actions'

const PRESET_COLORS = [
  '#3b82f6', '#10b981', '#f59e0b', '#ef4444',
  '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16',
]

export function TagManager({ initialTags }: { initialTags: Tag[] }) {
  const [open, setOpen]   = useState(false)
  const [tags, setTags]   = useState(initialTags)
  const [name, setName]   = useState('')
  const [color, setColor] = useState(PRESET_COLORS[0])
  const [saving, setSaving] = useState(false)
  const [error, setError]   = useState('')

  const handleCreate = async () => {
    if (!name.trim()) return
    setSaving(true); setError('')
    try {
      const tag = await actionCreateTag({ name: name.trim(), color })
      setTags(prev => [...prev, tag].sort((a, b) => a.name.localeCompare(b.name)))
      setName('')
    } catch (e: any) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id: number) => {
    if (!confirm('Supprimer ce tag ? Il sera retiré de tous les articles.')) return
    try {
      await actionDeleteTag(id)
      setTags(prev => prev.filter(t => t.id !== id))
    } catch (e: any) {
      setError(e.message)
    }
  }

  return (
    <div>
      <button
        onClick={() => setOpen(o => !o)}
        className="text-xs px-3 py-1.5 border border-border rounded-lg text-muted-foreground hover:text-foreground hover:border-primary transition-colors"
      >
        {open ? '✕ Fermer' : '🏷️ Gérer les tags'}
      </button>

      {open && (
        <div className="mt-4 border border-border rounded-xl p-5 bg-card space-y-4">
          <h3 className="text-sm font-semibold">Gestion des tags</h3>

          {/* Create */}
          <div className="flex flex-wrap items-end gap-3">
            <div>
              <label className="text-xs text-muted-foreground mb-1 block">Nom</label>
              <input
                value={name}
                onChange={e => setName(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleCreate()}
                placeholder="Nouveau tag…"
                className="bg-background border border-border rounded-lg px-3 py-1.5 text-sm w-40 focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>
            <div>
              <label className="text-xs text-muted-foreground mb-1 block">Couleur</label>
              <div className="flex gap-1.5">
                {PRESET_COLORS.map(c => (
                  <button
                    key={c}
                    onClick={() => setColor(c)}
                    className={`w-6 h-6 rounded-full border-2 transition-transform ${color === c ? 'border-white scale-110' : 'border-transparent'}`}
                    style={{ backgroundColor: c }}
                  />
                ))}
                <input
                  type="color"
                  value={color}
                  onChange={e => setColor(e.target.value)}
                  className="w-6 h-6 rounded cursor-pointer border-0 bg-transparent"
                />
              </div>
            </div>
            <button
              onClick={handleCreate}
              disabled={saving || !name.trim()}
              className="px-3 py-1.5 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:opacity-90 disabled:opacity-50"
            >
              {saving ? '…' : '+ Créer'}
            </button>
          </div>

          {error && <p className="text-xs text-destructive">{error}</p>}

          {/* Tags list */}
          {tags.length === 0 ? (
            <p className="text-sm text-muted-foreground">Aucun tag créé.</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {tags.map(tag => (
                <div key={tag.id} className="flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-medium"
                     style={{ backgroundColor: tag.color + '22', color: tag.color, border: `1px solid ${tag.color}44` }}>
                  <span>{tag.name}</span>
                  <button
                    onClick={() => handleDelete(tag.id)}
                    className="hover:opacity-70 text-xs leading-none ml-1"
                    title="Supprimer"
                  >✕</button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
