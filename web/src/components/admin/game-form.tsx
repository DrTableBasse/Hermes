"use client"

import { useId, useState, type FormEvent } from "react"
import { Button } from "@/components/ui/button"
import { api } from "@/lib/api/client"
import type { AdminGame, DiscordChannel, DiscordRole } from "@/lib/api/types"
import { cn } from "@/lib/cn"
import { adminErrorText, FIELD, LABEL } from "./form"

export type GameDraft = Omit<AdminGame, "active" | "position"> & { position: number }

/** Limites de `web-api/routes/content.py`. */
const NAME_MAX = 60
const TAGLINE_MAX = 120
const KEY_RE = /^[a-z0-9-]{1,32}$/
const COLOR_RE = /^#[0-9A-Fa-f]{6}$/

export function validateGame(d: GameDraft, creating: boolean): string | null {
  if (creating && !KEY_RE.test(d.key)) return "Clé : minuscules, chiffres et tirets (32 au plus), ex. « war-dogs »."
  if (!d.name.trim()) return "Nom requis."
  if ([...d.name.trim()].length > NAME_MAX) return `Nom : ${NAME_MAX} caractères maximum.`
  if (!COLOR_RE.test(d.color)) return "Couleur au format #RRGGBB."
  if ([...(d.tagline ?? "").trim()].length > TAGLINE_MAX) return `Accroche : ${TAGLINE_MAX} caractères maximum.`
  if (!Number.isInteger(d.position) || d.position < 0 || d.position > 10000) return "Position : entier de 0 à 10 000."
  return null
}

type Props = {
  initial: GameDraft
  creating: boolean
  roles: DiscordRole[] | null
  channels: DiscordChannel[] | null
  busy: boolean
  onSubmit: (draft: GameDraft) => void
  onCancel?: () => void
}

/** Champs d'un jeu : nom, couleur, visuel téléversé, accroche, rôle Discord, forum, position. */
export function GameForm({ initial, creating, roles, channels, busy, onSubmit, onCancel }: Props) {
  const ids = useId()
  const [d, setD] = useState(initial)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const set = <K extends keyof GameDraft>(k: K, v: GameDraft[K]) => setD(x => ({ ...x, [k]: v }))
  const error = validateGame(d, creating)
  const forums = channels?.filter(c => c.type === "forum") ?? null
  const f = (name: string) => `${ids}-${name}`

  async function upload(file: File | undefined) {
    if (!file) return
    setUploading(true)
    setUploadError(null)
    try {
      set("image", (await api.media.upload(file)).url)
    } catch (e) {
      setUploadError(adminErrorText(e))
    } finally {
      setUploading(false)
    }
  }

  function submit(e: FormEvent) {
    e.preventDefault()
    if (!error && !busy && !uploading) onSubmit({ ...d, name: d.name.trim(), tagline: d.tagline?.trim() || null })
  }

  return (
    <form onSubmit={submit} noValidate className="grid gap-4">
      <div className="grid gap-4 sm:grid-cols-2">
        {creating && (
          <div className="grid gap-1.5">
            <label htmlFor={f("key")} className={LABEL}>Clé (définitive)</label>
            <input id={f("key")} value={d.key} onChange={e => set("key", e.target.value.toLowerCase())} placeholder="war-dogs" className={FIELD} />
          </div>
        )}
        <div className="grid gap-1.5">
          <label htmlFor={f("name")} className={LABEL}>Nom</label>
          <input id={f("name")} value={d.name} maxLength={NAME_MAX} onChange={e => set("name", e.target.value)} className={FIELD} />
        </div>
        <div className="grid gap-1.5">
          <label htmlFor={f("color")} className={LABEL}>Couleur</label>
          <div className="flex gap-2">
            <input
              type="color"
              aria-label="Choisir la couleur"
              value={COLOR_RE.test(d.color) ? d.color : "#9B6BFF"}
              onChange={e => set("color", e.target.value.toUpperCase())}
              className="h-11 w-14 flex-none cursor-pointer rounded-xl border border-white/14 bg-transparent"
            />
            <input id={f("color")} value={d.color} onChange={e => set("color", e.target.value.trim())} className={FIELD} />
          </div>
        </div>
        <div className="grid gap-1.5">
          <label htmlFor={f("position")} className={LABEL}>Position</label>
          <input id={f("position")} inputMode="numeric" value={String(d.position)} onChange={e => set("position", Number(e.target.value))} className={FIELD} />
        </div>
      </div>
      <div className="grid gap-1.5">
        <label htmlFor={f("tagline")} className={LABEL}>Accroche</label>
        <input id={f("tagline")} value={d.tagline ?? ""} onChange={e => set("tagline", e.target.value)} placeholder="Une ligne affichée sur la carte du jeu" className={FIELD} />
        <span className={cn("text-xs tabular-nums", [...(d.tagline ?? "").trim()].length > TAGLINE_MAX ? "text-orange" : "text-muted")}>
          {[...(d.tagline ?? "").trim()].length} / {TAGLINE_MAX}
        </span>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="grid gap-1.5">
          <label htmlFor={f("role")} className={LABEL}>Rôle Discord</label>
          {roles ? (
            <select id={f("role")} value={d.discord_role_id ?? ""} onChange={e => set("discord_role_id", e.target.value || null)} className={FIELD}>
              <option value="">— Aucun —</option>
              {d.discord_role_id && !roles.some(r => r.id === d.discord_role_id) && <option value={d.discord_role_id}>Introuvable ({d.discord_role_id})</option>}
              {roles.map(r => <option key={r.id} value={r.id}>@{r.name}</option>)}
            </select>
          ) : (
            <input id={f("role")} inputMode="numeric" value={d.discord_role_id ?? ""} onChange={e => set("discord_role_id", e.target.value.trim() || null)} placeholder="Identifiant (bot muet)" className={FIELD} />
          )}
        </div>
        <div className="grid gap-1.5">
          <label htmlFor={f("forum")} className={LABEL}>Forum Discord</label>
          {forums ? (
            <select id={f("forum")} value={d.forum_channel_id ?? ""} onChange={e => set("forum_channel_id", e.target.value || null)} className={FIELD}>
              <option value="">— Aucun —</option>
              {d.forum_channel_id && !forums.some(c => c.id === d.forum_channel_id) && <option value={d.forum_channel_id}>Introuvable ({d.forum_channel_id})</option>}
              {forums.map(c => <option key={c.id} value={c.id}>#{c.name}</option>)}
            </select>
          ) : (
            <input id={f("forum")} inputMode="numeric" value={d.forum_channel_id ?? ""} onChange={e => set("forum_channel_id", e.target.value.trim() || null)} placeholder="Identifiant (bot muet)" className={FIELD} />
          )}
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        {d.image && (
          // eslint-disable-next-line @next/next/no-img-element -- aperçu du visuel téléversé
          <img src={d.image} alt="" className="h-14 w-24 rounded-lg object-cover" />
        )}
        <label className="cursor-pointer rounded-[10px] border border-white/14 bg-white/6 px-3 py-[7px] text-[13px] font-semibold has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-cyan">
          {uploading ? "Envoi…" : d.image ? "Changer le visuel" : "Téléverser un visuel"}
          <input type="file" accept="image/png,image/jpeg,image/webp,image/gif" className="sr-only" disabled={uploading} onChange={e => void upload(e.target.files?.[0])} />
        </label>
        {d.image && (
          <Button size="sm" variant="ghost" onClick={() => set("image", null)}>
            Retirer le visuel
          </Button>
        )}
        {uploadError && <span role="alert" className="text-sm text-orange">{uploadError}</span>}
      </div>
      {error && <p className="m-0 text-sm text-orange">{error}</p>}
      <div className="flex gap-2">
        <Button type="submit" size="sm" disabled={busy || uploading || error !== null}>
          {busy ? "…" : creating ? "Ajouter le jeu" : "Enregistrer"}
        </Button>
        {onCancel && (
          <Button size="sm" variant="ghost" onClick={onCancel}>
            Annuler
          </Button>
        )}
      </div>
    </form>
  )
}
