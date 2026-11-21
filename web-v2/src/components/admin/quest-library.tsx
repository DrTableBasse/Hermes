"use client"

import { useId, useState } from "react"
import { Button } from "@/components/ui/button"
import { Panel } from "@/components/ui/panel"
import { api } from "@/lib/api/client"
import type { QuestTemplate, QuestTemplateInput } from "@/lib/api/types"
import { cn } from "@/lib/cn"
import { ConfirmButton } from "./confirm-button"
import { adminErrorText } from "./form"
import { EMPTY_QUEST, QUEST_TYPES, QuestForm, questTypeLabel } from "./quest-form"

type Editing = { id: number | null; data: QuestTemplateInput } | null

const toInput = (t: QuestTemplate): QuestTemplateInput => ({
  title: t.title,
  description: t.description ?? "",
  quest_type: t.quest_type,
  target_value: t.target_value,
  xp_reward: t.xp_reward,
  icon: t.icon,
  is_enabled: t.is_enabled,
})

/** Bibliothèque des modèles de quêtes : filtre par type, création, édition, suppression confirmée. */
export function QuestLibrary({ templates: initial }: { templates: QuestTemplate[] }) {
  const ids = useId()
  const [templates, setTemplates] = useState(initial)
  const [editing, setEditing] = useState<Editing>(null)
  const [filter, setFilter] = useState("all")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function save(data: QuestTemplateInput) {
    if (!editing) return
    setBusy(true)
    setError(null)
    try {
      if (editing.id === null) {
        const created = await api.admin.createQuestTemplate(data)
        setTemplates(list => [...list, created])
      } else {
        const id = editing.id
        const updated = await api.admin.updateQuestTemplate(id, data)
        setTemplates(list => list.map(t => (t.id === id ? updated : t)))
      }
      setEditing(null)
    } catch (e) {
      setError(adminErrorText(e))
    } finally {
      setBusy(false)
    }
  }

  async function remove(id: number) {
    setError(null)
    try {
      await api.admin.deleteQuestTemplate(id)
      setTemplates(list => list.filter(t => t.id !== id))
    } catch (e) {
      setError(adminErrorText(e))
    }
  }

  const shown = templates.filter(t => filter === "all" || t.quest_type === filter)

  return (
    <Panel as="section" aria-labelledby={`${ids}-title`} className="grid gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id={`${ids}-title`} className="m-0 font-display text-xl font-extrabold">
          Bibliothèque ({templates.length})
        </h2>
        <Button size="sm" onClick={() => setEditing({ id: null, data: EMPTY_QUEST })}>
          Nouvelle quête
        </Button>
      </div>
      <div role="group" aria-label="Filtrer par condition" className="flex flex-wrap gap-1.5">
        {[{ value: "all", label: "Toutes" }, ...QUEST_TYPES].map(t => (
          <button
            key={t.value}
            type="button"
            aria-pressed={filter === t.value}
            onClick={() => setFilter(t.value)}
            className={cn(
              "rounded-full border px-3 py-1 text-xs font-semibold",
              filter === t.value ? "border-violet bg-violet/10 text-violet" : "border-line text-muted hover:text-fg",
            )}
          >
            {t.label}
          </button>
        ))}
      </div>
      {editing && (
        <QuestForm
          key={editing.id ?? "new"}
          initial={editing.data}
          editing={editing.id !== null}
          busy={busy}
          onSubmit={data => void save(data)}
          onCancel={() => setEditing(null)}
        />
      )}
      {error && (
        <p role="alert" className="m-0 text-sm text-orange">
          {error}
        </p>
      )}
      {shown.length === 0 ? (
        <p className="m-0 text-sm text-muted">Aucune quête pour ce filtre.</p>
      ) : (
        <ul className="m-0 grid list-none gap-2 p-0">
          {shown.map(t => (
            <li key={t.id} className={cn("flex flex-wrap items-center gap-3 rounded-xl border border-line px-4 py-3", !t.is_enabled && "opacity-60")}>
              <span className="text-xl" aria-hidden="true">
                {t.icon}
              </span>
              <div className="min-w-0 flex-1">
                <p className="m-0 text-sm font-semibold">
                  {t.title}
                  {!t.is_enabled && <span className="font-normal text-muted"> (hors rotation)</span>}
                </p>
                <p className="m-0 text-xs text-muted">
                  {questTypeLabel(t.quest_type)} · objectif {t.target_value} · +{t.xp_reward} XP
                </p>
              </div>
              <Button size="sm" variant="ghost" onClick={() => setEditing({ id: t.id, data: toInput(t) })}>
                Modifier
              </Button>
              <ConfirmButton question={`Supprimer « ${t.title} » ?`} confirmLabel="Supprimer" onConfirm={() => remove(t.id)}>
                Supprimer
              </ConfirmButton>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  )
}
