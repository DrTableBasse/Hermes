"use client"

import { useId, useState } from "react"
import { Button } from "@/components/ui/button"
import type { CatalogAchievement, Grade, ManagedRole, RoleRule, RoleRuleCondition, RoleRuleInput } from "@/lib/api/types"
import { RULE_CONDITIONS } from "@/lib/role-rules"
import { FIELD, LABEL } from "./form"
import { colorHex, hexColor } from "./roles-admin"

/** Règle complète, champs vides compris (`null`) : base de la comparaison d'une modification. */
export type RuleFields = Required<{ [K in keyof RoleRuleInput]: Exclude<RoleRuleInput[K], undefined> }>

export function ruleFields(rule: RoleRule): RuleFields {
  return {
    condition_type: rule.condition_type,
    condition_value: rule.condition_value,
    role_id: rule.role_id,
    create_role_name: rule.create_role_name,
    create_role_color: rule.create_role_color,
    remove_when_lost: rule.remove_when_lost,
    exclusive_group: rule.exclusive_group,
    active: rule.active,
  }
}

type Props = {
  title: string
  submitLabel: string
  initial?: RoleRule
  /** Rôles proposés comme cible (gérables par l'acteur et par Hermes). */
  roles: ManagedRole[]
  achievements: CatalogAchievement[]
  grades: Grade[]
  /** Reçoit la règle complète ; renvoie le message d'erreur à afficher, ou `null` en cas de succès. */
  onSubmit: (fields: RuleFields) => Promise<string | null>
  onCancel: () => void
}

const RADIO = "flex items-center gap-2 text-sm text-msg"
const CHECK = "flex items-start gap-2 text-sm text-msg"

/** Valeur par défaut quand la condition change : premier grade / succès, sinon champ vide. */
function defaultValue(type: RoleRuleCondition, grades: Grade[], achievements: CatalogAchievement[]): string {
  if (type === "grade") return grades[0]?.slug ?? ""
  if (type === "achievement") return achievements[0] ? String(achievements[0].id) : ""
  return ""
}

/** Création ou modification d'une règle automatique (condition, cible, options). */
export function RoleRuleForm({ title, submitLabel, initial, roles, achievements, grades, onSubmit, onCancel }: Props) {
  const ids = useId()
  const [type, setType] = useState<RoleRuleCondition>(initial?.condition_type ?? "voice_hours")
  const [value, setValue] = useState(initial?.condition_value ?? "")
  const [target, setTarget] = useState<"role" | "create">(initial && !initial.role_id && initial.create_role_name ? "create" : "role")
  const [roleId, setRoleId] = useState(initial?.role_id ?? "")
  const [createName, setCreateName] = useState(initial?.create_role_name ?? "")
  const [createColor, setCreateColor] = useState(colorHex(initial?.create_role_color ?? 0))
  const [removeWhenLost, setRemoveWhenLost] = useState(initial?.remove_when_lost ?? false)
  const [group, setGroup] = useState(initial?.exclusive_group ?? "")
  const [active, setActive] = useState(initial?.active ?? true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const canCreate = type === "achievement"
  const mode = canCreate ? target : "role"
  // Rôle actuel absent des rôles gérables (introuvable, au-dessus) : gardé en option pour ne pas le perdre.
  const current = initial?.role_id && !roles.some(r => r.id === initial.role_id) ? initial : null

  function changeType(next: RoleRuleCondition) {
    setType(next)
    setValue(defaultValue(next, grades, achievements))
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    const trimmed = value.trim()
    if (!trimmed) return setError("Indique une valeur pour la condition.")
    if (mode === "role" && !roleId) return setError("Choisis le rôle donné par la règle.")
    if (mode === "create" && !createName.trim()) return setError("Donne un nom au rôle à créer.")
    setError(null)
    setBusy(true)
    const failure = await onSubmit({
      condition_type: type,
      condition_value: trimmed,
      role_id: mode === "role" ? roleId : null,
      create_role_name: mode === "create" ? createName.trim() : null,
      create_role_color: mode === "create" ? hexColor(createColor) : null,
      remove_when_lost: removeWhenLost,
      exclusive_group: group.trim() || null,
      active,
    })
    setBusy(false)
    if (failure) setError(failure)
  }

  return (
    <section aria-labelledby={`${ids}-title`} className="grid gap-4 rounded-[20px] border border-line bg-[rgb(19_22_42/0.92)] px-5 py-4">
      <h2 id={`${ids}-title`} className="m-0 font-display text-lg font-bold">
        {title}
      </h2>
      <form onSubmit={e => void submit(e)} className="grid gap-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="grid content-start gap-1.5">
            <label htmlFor={`${ids}-type`} className={LABEL}>
              Condition
            </label>
            <select id={`${ids}-type`} className={FIELD} value={type} onChange={e => changeType(e.target.value as RoleRuleCondition)}>
              {RULE_CONDITIONS.map(c => (
                <option key={c.key} value={c.key}>
                  {c.label}
                </option>
              ))}
            </select>
          </div>
          <div className="grid content-start gap-1.5">
            <label htmlFor={`${ids}-value`} className={LABEL}>
              Valeur
            </label>
            {type === "grade" || type === "achievement" ? (
              <select id={`${ids}-value`} className={FIELD} value={value} onChange={e => setValue(e.target.value)}>
                {type === "grade"
                  ? grades.map(g => (
                      <option key={g.slug} value={g.slug}>
                        {g.name} (niveau {g.level_min})
                      </option>
                    ))
                  : achievements.map(a => (
                      <option key={a.id} value={String(a.id)}>
                        {a.icon ? `${a.icon} ` : ""}
                        {a.name}
                      </option>
                    ))}
              </select>
            ) : (
              <input
                id={`${ids}-value`}
                type="number"
                min={0}
                step={type === "voice_hours" ? "any" : 1}
                inputMode={type === "voice_hours" ? "decimal" : "numeric"}
                className={FIELD}
                value={value}
                onChange={e => setValue(e.target.value)}
              />
            )}
          </div>
        </div>

        <fieldset className="m-0 grid gap-3 border-0 p-0">
          <legend className={`${LABEL} mb-1.5 p-0`}>Rôle donné</legend>
          {canCreate && (
            <div className="flex flex-wrap gap-x-5 gap-y-2">
              <label className={RADIO}>
                <input type="radio" name={`${ids}-target`} checked={target === "role"} onChange={() => setTarget("role")} className="accent-violet" />
                Rôle existant
              </label>
              <label className={RADIO}>
                <input type="radio" name={`${ids}-target`} checked={target === "create"} onChange={() => setTarget("create")} className="accent-violet" />
                Créer au premier déblocage
              </label>
            </div>
          )}
          {mode === "role" ? (
            <div className="grid max-w-sm gap-1.5">
              <label htmlFor={`${ids}-role`} className={LABEL}>
                Rôle
              </label>
              <select id={`${ids}-role`} className={FIELD} value={roleId} onChange={e => setRoleId(e.target.value)}>
                <option value="">Choisir un rôle</option>
                {current && <option value={current.role_id!}>{current.role_name ?? "rôle introuvable"}</option>}
                {roles.map(r => (
                  <option key={r.id} value={r.id}>
                    {r.name}
                  </option>
                ))}
              </select>
            </div>
          ) : (
            <div className="grid gap-4 sm:grid-cols-[1fr_auto]">
              <div className="grid gap-1.5">
                <label htmlFor={`${ids}-cname`} className={LABEL}>
                  Nom du rôle à créer
                </label>
                <input id={`${ids}-cname`} className={FIELD} maxLength={100} value={createName} onChange={e => setCreateName(e.target.value)} />
              </div>
              <div className="grid gap-1.5">
                <label htmlFor={`${ids}-ccolor`} className={LABEL}>
                  Couleur du rôle
                </label>
                <input
                  id={`${ids}-ccolor`}
                  type="color"
                  className="h-11 w-20 cursor-pointer rounded-xl border border-white/14 bg-transparent p-1"
                  value={createColor}
                  onChange={e => setCreateColor(e.target.value)}
                />
              </div>
            </div>
          )}
        </fieldset>

        <div className="grid gap-3 sm:grid-cols-2">
          <div className="grid content-start gap-1.5">
            <label htmlFor={`${ids}-group`} className={LABEL}>
              Groupe exclusif (facultatif)
            </label>
            <input
              id={`${ids}-group`}
              className={FIELD}
              maxLength={50}
              value={group}
              aria-describedby={`${ids}-group-hint`}
              onChange={e => setGroup(e.target.value)}
            />
            <p id={`${ids}-group-hint`} className="m-0 text-xs text-muted">
              Un seul rôle du groupe à la fois : celui de la règle au seuil le plus élevé.
            </p>
          </div>
          <div className="grid content-start gap-2 sm:pt-7">
            <label className={CHECK}>
              <input type="checkbox" checked={removeWhenLost} onChange={e => setRemoveWhenLost(e.target.checked)} className="mt-0.5 size-4 accent-violet" />
              Retirer le rôle si la condition est perdue
            </label>
            <label className={CHECK}>
              <input type="checkbox" checked={active} onChange={e => setActive(e.target.checked)} className="mt-0.5 size-4 accent-violet" />
              Règle active
            </label>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <Button type="submit" size="sm" disabled={busy}>
            {busy ? "Enregistrement…" : submitLabel}
          </Button>
          <Button type="button" size="sm" variant="ghost" onClick={onCancel}>
            Annuler
          </Button>
          {error && (
            <p role="alert" className="m-0 text-sm text-orange">
              {error}
            </p>
          )}
        </div>
      </form>
    </section>
  )
}
