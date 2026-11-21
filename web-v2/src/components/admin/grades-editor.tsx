"use client"

import { useId, useState, type FormEvent } from "react"
import { Button } from "@/components/ui/button"
import { GradeBadge } from "@/components/ui/grade-badge"
import { Panel } from "@/components/ui/panel"
import { api } from "@/lib/api/client"
import type { Grade } from "@/lib/api/types"
import { cn } from "@/lib/cn"
import { adminErrorText, FIELD, type Feedback } from "./form"

const NAME_MAX = 40
const LEVEL_MAX = 1000
const COLOR_RE = /^#[0-9A-Fa-f]{6}$/
/** Le premier grade commence au niveau 1 (règle de `PUT /admin/grades/{slug}`). */
const FIRST_SLUG = "recrue"

export function validateGrade(g: Grade): string | null {
  if (!g.name.trim()) return "Nom requis."
  if ([...g.name.trim()].length > NAME_MAX) return `Nom : ${NAME_MAX} caractères maximum.`
  if (!COLOR_RE.test(g.color)) return "Couleur au format #RRGGBB."
  if (!Number.isInteger(g.level_min) || g.level_min < 1 || g.level_min > LEVEL_MAX) return `Niveau minimal : 1 à ${LEVEL_MAX}.`
  if (g.slug === FIRST_SLUG && g.level_min !== 1) return "La recrue commence toujours au niveau 1."
  return null
}

function GradeRow({ grade }: { grade: Grade }) {
  const ids = useId()
  const [g, setG] = useState(grade)
  const [busy, setBusy] = useState(false)
  const [feedback, setFeedback] = useState<Feedback>(null)
  const error = validateGrade(g)
  const set = <K extends keyof Grade>(k: K, v: Grade[K]) => {
    setFeedback(null)
    setG(x => ({ ...x, [k]: v }))
  }

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (error || busy) return
    setBusy(true)
    setFeedback(null)
    try {
      await api.admin.updateGrade(g.slug, { name: g.name.trim(), color: g.color.toUpperCase(), level_min: g.level_min })
      setFeedback({ kind: "ok", text: "Enregistré." })
    } catch (err) {
      setFeedback({ kind: "error", text: adminErrorText(err) })
    } finally {
      setBusy(false)
    }
  }

  const locked = g.slug === FIRST_SLUG
  return (
    <li>
      <form onSubmit={submit} noValidate aria-label={`Grade ${grade.name}`} className="grid gap-2 rounded-xl border border-line p-4">
        <div className="grid items-end gap-3 sm:grid-cols-[1.4fr_1fr_0.8fr_auto]">
          <label className="grid gap-1 text-sm font-semibold">
            Nom
            <input value={g.name} onChange={e => set("name", e.target.value)} className={FIELD} />
          </label>
          <div className="grid gap-1 text-sm font-semibold">
            <label htmlFor={`${ids}-color`}>Couleur</label>
            <div className="flex gap-2">
              <input
                type="color"
                aria-label={`Choisir la couleur de ${grade.name}`}
                value={COLOR_RE.test(g.color) ? g.color : "#9B6BFF"}
                onChange={e => set("color", e.target.value.toUpperCase())}
                className="h-11 w-12 flex-none cursor-pointer rounded-xl border border-white/14 bg-transparent"
              />
              <input id={`${ids}-color`} value={g.color} onChange={e => set("color", e.target.value.trim())} className={FIELD} />
            </div>
          </div>
          <label className="grid gap-1 text-sm font-semibold">
            Niveau minimal
            <input
              inputMode="numeric"
              value={String(g.level_min)}
              readOnly={locked}
              aria-describedby={locked ? `${ids}-locked` : undefined}
              onChange={e => set("level_min", Number(e.target.value))}
              className={cn(FIELD, locked && "opacity-60")}
            />
          </label>
          <Button type="submit" size="sm" disabled={busy || error !== null}>
            {busy ? "…" : "Enregistrer"}
          </Button>
        </div>
        <div className="flex flex-wrap items-center gap-3 text-sm">
          {COLOR_RE.test(g.color) && g.name.trim() && <GradeBadge grade={{ name: g.name.trim(), slug: g.slug, color: g.color }} />}
          {locked && (
            <span id={`${ids}-locked`} className="text-muted">
              Premier grade : niveau 1 fixe.
            </span>
          )}
          {error ? (
            <span className="text-orange">{error}</span>
          ) : feedback ? (
            <span role={feedback.kind === "error" ? "alert" : "status"} className={feedback.kind === "error" ? "text-orange" : "text-green"}>
              {feedback.text}
            </span>
          ) : null}
        </div>
      </form>
    </li>
  )
}

/** Grades de progression : nom, couleur et niveau d'entrée (deux grades ne commencent pas au même niveau). */
export function GradesEditor({ grades }: { grades: Grade[] }) {
  const ids = useId()
  return (
    <Panel as="section" aria-labelledby={`${ids}-title`} className="grid gap-4">
      <h2 id={`${ids}-title`} className="m-0 font-display text-xl font-extrabold">
        Grades
      </h2>
      <ol className="m-0 grid list-none gap-3 p-0">
        {[...grades].sort((a, b) => a.level_min - b.level_min).map(g => (
          <GradeRow key={g.slug} grade={g} />
        ))}
      </ol>
    </Panel>
  )
}
