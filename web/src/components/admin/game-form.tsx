"use client"

import { useId, useState, type FormEvent } from "react"
import { Button } from "@/components/ui/button"
import { api } from "@/lib/api/client"
import type { DiscordChannel, DiscordRole, Snowflake } from "@/lib/api/types"
import { cn } from "@/lib/cn"
import { adminErrorText, FIELD, LABEL } from "./form"

/** Champs éditables d'un jeu (création ou modification). */
export type GameDraft = {
  key: string
  name: string
  emoji: string
  color: string
  command_name: string
  tagline: string | null
  image: string | null
  position: number
  discord_role_id: Snowflake | null
  forum_channel_id: Snowflake | null
}

/** Limites de `web-api/routes/content.py` et `web-api/game_rules.py`. */
const NAME_MAX = 60
const TAGLINE_MAX = 120
const EMOJI_MAX = 32
const KEY_RE = /^[a-z0-9-]{1,32}$/
const COMMAND_RE = /^[a-z0-9_-]{1,32}$/
const COLOR_RE = /^#[0-9A-Fa-f]{6}$/

/** « Apex Légendes ! » → « apex-legendes » : clé et commande proposées depuis le nom. */
export function slugify(name: string): string {
  return name
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+/, "")
    .slice(0, 32)
    .replace(/-+$/, "")
}

/** Contrôle côté navigateur ; l'API reste juge (unicité, émoji valide : 422 affiché). */
export function validateGame(d: GameDraft, creating: boolean): string | null {
  if (!d.name.trim()) return "Nom requis."
  if ([...d.name.trim()].length > NAME_MAX) return `Nom : ${NAME_MAX} caractères maximum.`
  if (creating && !KEY_RE.test(d.key)) return "Clé : minuscules, chiffres et tirets (32 au plus), ex. « war-dogs »."
  if (!d.emoji.trim()) return "Émoji requis (celui du message de rôles par réaction)."
  if ([...d.emoji.trim()].length > EMOJI_MAX) return `Émoji : ${EMOJI_MAX} caractères maximum.`
  if (!COLOR_RE.test(d.color)) return "Couleur au format #RRGGBB."
  if (!COMMAND_RE.test(d.command_name)) return "Commande : minuscules, chiffres, « - » ou « _ » (32 au plus), sans barre oblique."
  if ([...(d.tagline ?? "").trim()].length > TAGLINE_MAX) return `Accroche : ${TAGLINE_MAX} caractères maximum.`
  if (!Number.isInteger(d.position) || d.position < 0 || d.position > 10000) return "Position : entier de 0 à 10 000."
  return null
}

type Props = {
  initial: GameDraft
  creating: boolean
  /** Rôle et forum existants rattachables (admin seulement). */
  canAttach?: boolean
  roles: DiscordRole[] | null
  channels: DiscordChannel[] | null
  busy: boolean
  onSubmit: (draft: GameDraft) => void
  onCancel?: () => void
}

/**
 * Champs d'un jeu. Création : nom, émoji, couleur, commande (proposée depuis le nom), accroche, visuel ;
 * rôle et forum viennent du provisionnement. Modification : position en plus, et rôle et forum
 * pour un admin (`canAttach`).
 */
export function GameForm({ initial, creating, canAttach = false, roles, channels, busy, onSubmit, onCancel }: Props) {
  const ids = useId()
  const [d, setD] = useState(initial)
  // Clé et commande suivent le nom tant qu'elles n'ont pas été saisies à la main.
  const [typed, setTyped] = useState({ key: !creating, command: !creating })
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const set = <K extends keyof GameDraft>(k: K, v: GameDraft[K]) => setD(x => ({ ...x, [k]: v }))
  const error = validateGame(d, creating)
  const forums = channels?.filter(c => c.type === "forum") ?? null
  const f = (name: string) => `${ids}-${name}`

  function rename(name: string) {
    const slug = slugify(name)
    setD(x => ({
      ...x,
      name,
      key: typed.key ? x.key : slug,
      command_name: typed.command ? x.command_name : slug,
    }))
  }

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
    if (!error && !busy && !uploading) {
      onSubmit({ ...d, name: d.name.trim(), emoji: d.emoji.trim(), tagline: d.tagline?.trim() || null })
    }
  }

  return (
    <form onSubmit={submit} noValidate className="grid gap-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="grid gap-1.5">
          <label htmlFor={f("name")} className={LABEL}>Nom</label>
          <input id={f("name")} value={d.name} maxLength={NAME_MAX} onChange={e => rename(e.target.value)} className={FIELD} />
        </div>
        <div className="grid gap-1.5">
          <label htmlFor={f("emoji")} className={LABEL}>Émoji</label>
          <input
            id={f("emoji")}
            value={d.emoji}
            onChange={e => set("emoji", e.target.value)}
            placeholder="🎮"
            aria-describedby={f("emoji-help")}
            className={FIELD}
          />
          <span id={f("emoji-help")} className="text-xs text-muted">
            Un seul émoji, propre au jeu : il sert au message de rôles par réaction.
          </span>
        </div>
        {creating && (
          <div className="grid gap-1.5">
            <label htmlFor={f("key")} className={LABEL}>Clé (définitive)</label>
            <input
              id={f("key")}
              value={d.key}
              onChange={e => {
                setTyped(t => ({ ...t, key: true }))
                set("key", e.target.value.toLowerCase())
              }}
              placeholder="war-dogs"
              className={FIELD}
            />
          </div>
        )}
        <div className="grid gap-1.5">
          <label htmlFor={f("command")} className={LABEL}>Commande</label>
          <div className="flex items-center gap-1.5">
            <span className="font-mono text-muted" aria-hidden="true">/</span>
            <input
              id={f("command")}
              value={d.command_name}
              onChange={e => {
                setTyped(t => ({ ...t, command: true }))
                set("command_name", e.target.value.toLowerCase().replace(/^\//, ""))
              }}
              placeholder="war-dogs"
              className={cn(FIELD, "font-mono")}
            />
          </div>
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
        {!creating && (
          <div className="grid gap-1.5">
            <label htmlFor={f("position")} className={LABEL}>Position</label>
            <input id={f("position")} inputMode="numeric" value={String(d.position)} onChange={e => set("position", Number(e.target.value))} className={FIELD} />
          </div>
        )}
      </div>
      <div className="grid gap-1.5">
        <label htmlFor={f("tagline")} className={LABEL}>Accroche</label>
        <input id={f("tagline")} value={d.tagline ?? ""} onChange={e => set("tagline", e.target.value)} placeholder="Une ligne affichée sur la carte du jeu" className={FIELD} />
        <span className={cn("text-xs tabular-nums", [...(d.tagline ?? "").trim()].length > TAGLINE_MAX ? "text-orange" : "text-muted")}>
          {[...(d.tagline ?? "").trim()].length} / {TAGLINE_MAX}
        </span>
      </div>
      {!creating && canAttach && (
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
      )}
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
      {creating && (
        <p className="m-0 text-sm text-muted">
          À l’enregistrement, Hermes crée (ou reprend s’ils existent déjà) le rôle et le forum du jeu, puis inscrit la commande.
        </p>
      )}
      <div className="flex gap-2">
        <Button type="submit" size="sm" disabled={busy || uploading || error !== null}>
          {busy ? "En cours…" : creating ? "Ajouter le jeu" : "Enregistrer"}
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
