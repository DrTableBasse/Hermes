"use client"

import { useId, useState, type FormEvent } from "react"
import { Button } from "@/components/ui/button"
import type { QuestTemplateInput } from "@/lib/api/types"
import { FIELD, LABEL } from "./form"

/** Types acceptés par `QUEST_TYPES` (web-api/routes/admin.py). */
export const QUEST_TYPES = [
  { value: "messages", label: "Messages" },
  { value: "voice_minutes", label: "Minutes en vocal" },
  { value: "bumps", label: "Bumps" },
  { value: "invites", label: "Invitations" },
  { value: "images_posted", label: "Images et vidéos" },
  { value: "reactions_given", label: "Réactions données" },
] as const

export const questTypeLabel = (value: string) => QUEST_TYPES.find(t => t.value === value)?.label ?? value

export const EMPTY_QUEST: QuestTemplateInput = {
  title: "",
  description: "",
  quest_type: "messages",
  target_value: 100,
  xp_reward: 50,
  icon: "📋",
  is_enabled: true,
}

type Props = {
  initial: QuestTemplateInput
  editing: boolean
  busy: boolean
  onSubmit: (data: QuestTemplateInput) => void
  onCancel: () => void
}

/** Création ou modification d'un modèle de quête. */
export function QuestForm({ initial, editing, busy, onSubmit, onCancel }: Props) {
  const ids = useId()
  const [form, setForm] = useState(initial)
  const set = <K extends keyof QuestTemplateInput>(key: K, value: QuestTemplateInput[K]) => setForm(f => ({ ...f, [key]: value }))
  const target = Number(form.target_value)
  const xp = Number(form.xp_reward)
  const error = !form.title.trim()
    ? "Titre requis."
    : !Number.isInteger(target) || target < 1
      ? "Objectif : nombre entier, au moins 1."
      : !Number.isInteger(xp) || xp < 1
        ? "Récompense : nombre entier d’XP, au moins 1."
        : null

  function submit(e: FormEvent) {
    e.preventDefault()
    if (error || busy) return
    onSubmit({ ...form, title: form.title.trim(), description: form.description?.trim() || null })
  }

  const field = (id: string) => `${ids}-${id}`
  return (
    <form onSubmit={submit} noValidate className="grid gap-4 rounded-2xl border border-line bg-white/3 p-4">
      <h3 className="m-0 font-semibold">{editing ? "Modifier la quête" : "Nouvelle quête"}</h3>
      <div className="grid gap-4 sm:grid-cols-[5rem_1fr_1fr]">
        <div className="grid gap-1.5">
          <label htmlFor={field("icon")} className={LABEL}>
            Icône
          </label>
          <input id={field("icon")} value={form.icon} maxLength={8} onChange={e => set("icon", e.target.value)} className={`${FIELD} text-center`} />
        </div>
        <div className="grid gap-1.5">
          <label htmlFor={field("title")} className={LABEL}>
            Titre
          </label>
          <input id={field("title")} value={form.title} maxLength={120} onChange={e => set("title", e.target.value)} className={FIELD} />
        </div>
        <div className="grid gap-1.5">
          <label htmlFor={field("type")} className={LABEL}>
            Condition
          </label>
          <select id={field("type")} value={form.quest_type} onChange={e => set("quest_type", e.target.value)} className={FIELD}>
            {QUEST_TYPES.map(t => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </div>
      </div>
      <div className="grid gap-4 sm:grid-cols-[2fr_1fr_1fr]">
        <div className="grid gap-1.5">
          <label htmlFor={field("desc")} className={LABEL}>
            Description
          </label>
          <input id={field("desc")} value={form.description ?? ""} onChange={e => set("description", e.target.value)} className={FIELD} />
        </div>
        <div className="grid gap-1.5">
          <label htmlFor={field("target")} className={LABEL}>
            Objectif
          </label>
          <input
            id={field("target")}
            inputMode="numeric"
            value={String(form.target_value)}
            onChange={e => set("target_value", Number(e.target.value))}
            className={FIELD}
          />
        </div>
        <div className="grid gap-1.5">
          <label htmlFor={field("xp")} className={LABEL}>
            Récompense (XP)
          </label>
          <input id={field("xp")} inputMode="numeric" value={String(form.xp_reward)} onChange={e => set("xp_reward", Number(e.target.value))} className={FIELD} />
        </div>
      </div>
      <label className="inline-flex items-center gap-2 text-sm">
        <input type="checkbox" checked={form.is_enabled ?? true} onChange={e => set("is_enabled", e.target.checked)} className="size-4 accent-violet" />
        Dans la rotation hebdomadaire
      </label>
      {error && <p className="m-0 text-sm text-orange">{error}</p>}
      <div className="flex gap-2">
        <Button type="submit" size="sm" disabled={busy || error !== null}>
          {busy ? "…" : editing ? "Enregistrer" : "Créer"}
        </Button>
        <Button size="sm" variant="ghost" onClick={onCancel}>
          Annuler
        </Button>
      </div>
    </form>
  )
}
