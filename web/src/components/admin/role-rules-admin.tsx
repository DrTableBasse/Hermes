"use client"

import { Plus } from "lucide-react"
import { useId, useMemo, useState } from "react"
import { Button } from "@/components/ui/button"
import { api } from "@/lib/api/client"
import type {
  CatalogAchievement,
  Grade,
  ManagedRole,
  RoleRule,
  RoleRuleApplyInput,
  RoleRuleInput,
  RoleRulePreview,
} from "@/lib/api/types"
import { plural } from "@/lib/jobs"
import { PERMISSIONS } from "@/lib/permissions"
import { conditionText } from "@/lib/role-rules"
import { ConfirmButton } from "./confirm-button"
import { adminErrorText } from "./form"
import { JobProgress } from "./job-progress"
import { RoleRuleForm, ruleFields, type RuleFields } from "./role-rule-form"

type Props = {
  initialRules: RoleRule[]
  roles: ManagedRole[]
  achievements: CatalogAchievement[]
  grades: Grade[]
  /** Droit `members.roles` : retrait de l'ancien rôle d'une règle proposé à la validation. */
  canMemberRoles: boolean
}

type PreviewState = {
  id: number
  status: "loading" | "ok" | "error"
  data?: RoleRulePreview
  error?: string
  /** Validée : « Valider » attend un nouvel aperçu. */
  validated?: boolean
  jobs?: { apply: string; remove: string | null }
  applyError?: string
}

type OldRole = { id: string; name: string; members: number }

/** Nombre de noms affichés par liste d'aperçu (le total reste annoncé). */
const PREVIEW_NAMES = 100

const NOT_RELOADED = " Hermes n’a pas pu recharger ses règles : elles prendront effet à son redémarrage."

/** Règles automatiques : tableau, création/modification, aperçu puis validation, suppression. */
export function RoleRulesAdmin({ initialRules, roles, achievements, grades, canMemberRoles }: Props) {
  const ids = useId()
  const [rules, setRules] = useState(initialRules)
  const [form, setForm] = useState<{ kind: "create" } | { kind: "edit"; id: number } | null>(null)
  const [preview, setPreview] = useState<PreviewState | null>(null)
  const [removeOld, setRemoveOld] = useState(false)
  // Ancien rôle renvoyé par un PATCH : nombre de membres plus frais que celui de la liste des rôles.
  const [oldRoles, setOldRoles] = useState<Map<string, OldRole>>(new Map())
  const [success, setSuccess] = useState("")
  const [error, setError] = useState<string | null>(null)

  const gradeNames = useMemo(() => new Map(grades.map(g => [g.slug, g.name])), [grades])
  const label = (rule: RoleRule) => conditionText(rule, { grades: gradeNames })
  const targetRoles = roles.filter(r => r.editable)

  /** Ancien rôle retirable à la validation : mémorisé par web-api et différent du rôle actuel. */
  function oldRoleOf(rule: RoleRule): OldRole | null {
    const id = rule.previous_role_id
    if (!id || id === rule.role_id) return null
    const known = oldRoles.get(id)
    if (known) return known
    const role = roles.find(r => r.id === id)
    return role ? { id: role.id, name: role.name, members: role.members } : null
  }

  function announce(text: string) {
    setError(null)
    setSuccess(text)
  }

  const replaceRule = (rule: RoleRule) => setRules(list => list.map(r => (r.id === rule.id ? rule : r)))

  /** Champs envoyés à la création : les vides sont omis (valeurs par défaut de web-api). */
  async function create(fields: RuleFields): Promise<string | null> {
    const input = Object.fromEntries(Object.entries(fields).filter(([, v]) => v !== null)) as unknown as RoleRuleInput
    try {
      const res = await api.admin.createRoleRule(input)
      setRules(list => [...list, res.rule])
      setForm(null)
      announce(`Règle créée en mode aperçu.${res.reloaded ? "" : NOT_RELOADED}`)
      return null
    } catch (e) {
      return adminErrorText(e)
    }
  }

  /** Modification : seuls les champs changés partent (web-api ne revalide le rôle que s'il change). */
  async function update(rule: RoleRule, fields: RuleFields): Promise<string | null> {
    const before = ruleFields(rule)
    const changes = Object.fromEntries(
      (Object.keys(fields) as Array<keyof RuleFields>).filter(k => fields[k] !== before[k]).map(k => [k, fields[k]]),
    ) as Partial<RoleRuleInput>
    if (Object.keys(changes).length === 0) return "Aucun changement à enregistrer."
    try {
      const res = await api.admin.updateRoleRule(rule.id, changes)
      replaceRule(res.rule)
      const old = res.previous_role
      if (old) setOldRoles(map => new Map(map).set(old.id, old))
      if (preview?.id === rule.id) setPreview(null) // aperçu périmé
      setForm(null)
      announce(`Règle enregistrée.${res.reloaded ? "" : NOT_RELOADED}`)
      return null
    } catch (e) {
      return adminErrorText(e)
    }
  }

  async function remove(rule: RoleRule) {
    setSuccess("")
    setError(null)
    try {
      const res = await api.admin.deleteRoleRule(rule.id)
      setRules(list => list.filter(r => r.id !== rule.id))
      if (preview?.id === rule.id) setPreview(null)
      if (form?.kind === "edit" && form.id === rule.id) setForm(null)
      announce(`Règle supprimée.${res.reloaded ? "" : NOT_RELOADED}`)
    } catch (e) {
      setError(adminErrorText(e))
    }
  }

  async function showPreview(rule: RoleRule) {
    setRemoveOld(false)
    setPreview({ id: rule.id, status: "loading" })
    try {
      const data = await api.admin.previewRoleRule(rule.id)
      setPreview(p => (p?.id === rule.id ? { id: rule.id, status: "ok", data } : p))
    } catch (e) {
      setPreview(p => (p?.id === rule.id ? { id: rule.id, status: "error", error: adminErrorText(e) } : p))
    }
  }

  /** Applique la règle (travail du bot) puis la passe en mode « Appliquée » (réconciliation). */
  async function validate(rule: RoleRule) {
    const old = removeOld && canMemberRoles ? oldRoleOf(rule) : null
    const body: RoleRuleApplyInput = old
      ? { confirm: true, remove_previous_role_id: old.id, confirm_previous_members: old.members }
      : { confirm: true }
    const patch = (next: Partial<PreviewState>) => setPreview(p => (p?.id === rule.id ? { ...p, ...next } : p))
    patch({ applyError: undefined })
    let jobs: PreviewState["jobs"]
    try {
      const res = await api.admin.applyRoleRule(rule.id, body)
      jobs = { apply: res.job_id, remove: res.remove_job_id }
      patch({ jobs, validated: true })
    } catch (e) {
      patch({ applyError: adminErrorText(e) })
      return
    }
    setRemoveOld(false)
    if (rule.reconcile) return
    try {
      const res = await api.admin.updateRoleRule(rule.id, { reconcile: true, preview_seen: true })
      replaceRule(res.rule)
      if (!res.reloaded) announce(NOT_RELOADED.trim())
    } catch (e) {
      patch({ applyError: `Règle appliquée, mais elle reste en mode aperçu : ${adminErrorText(e)}` })
    }
  }

  function validateQuestion(rule: RoleRule): string {
    const data = preview?.id === rule.id ? preview.data : undefined
    if (!data) return `Appliquer « ${label(rule)} » ?`
    const g = data.gain.length
    const l = data.lose.length
    const old = removeOld && canMemberRoles ? oldRoleOf(rule) : null
    return (
      `Appliquer « ${label(rule)} » : ${plural(g, "membre")} gagne${g > 1 ? "nt" : ""} le rôle, ${l} le perd${l > 1 ? "ent" : ""}` +
      (old ? `, et retirer « ${old.name} » à ${plural(old.members, "membre")}` : "") +
      " ?"
    )
  }

  const editing = form?.kind === "edit" ? rules.find(r => r.id === form.id) : undefined
  const previewed = preview ? rules.find(r => r.id === preview.id) : undefined

  return (
    <div className="grid gap-6">
      <div className="flex flex-wrap items-center gap-3">
        <Button
          size="sm"
          aria-expanded={form?.kind === "create"}
          onClick={() => setForm(f => (f?.kind === "create" ? null : { kind: "create" }))}
        >
          <Plus aria-hidden="true" className="size-4" />
          Nouvelle règle
        </Button>
        <p role="status" aria-label="Règles" className="m-0 text-sm text-green">
          {success}
        </p>
        {error && (
          <p role="alert" className="m-0 text-sm text-orange">
            {error}
          </p>
        )}
      </div>

      {form?.kind === "create" && (
        <RoleRuleForm
          title="Nouvelle règle"
          submitLabel="Créer la règle"
          roles={targetRoles}
          achievements={achievements}
          grades={grades}
          onSubmit={create}
          onCancel={() => setForm(null)}
        />
      )}

      <div className="overflow-x-auto rounded-[20px] border border-line">
        <table className="w-full border-collapse text-left text-sm">
          <caption className="sr-only">Règles automatiques</caption>
          <thead className="text-muted">
            <tr>
              {["Condition", "Rôle donné", "Retiré si perdu", "Mode", "Actif", "Actions"].map(h => (
                <th key={h} scope="col" className="px-4 py-3 font-semibold whitespace-nowrap">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rules.length === 0 && (
              <tr className="border-t border-line">
                <td colSpan={6} className="px-4 py-3 text-muted">
                  Aucune règle pour l’instant.
                </td>
              </tr>
            )}
            {rules.map(rule => {
              const seen = preview?.id === rule.id && preview.status === "ok" && !preview.data?.missing_role && !preview.validated
              return (
                <tr key={rule.id} className={rule.active ? "border-t border-line" : "border-t border-line text-muted"}>
                  <td className="px-4 py-3 font-semibold">{label(rule)}</td>
                  <td className="px-4 py-3">
                    {rule.missing_role ? (
                      <span className="font-semibold text-orange">rôle introuvable</span>
                    ) : rule.role_id ? (
                      (rule.role_name ?? "—")
                    ) : (
                      `créé au déblocage (${rule.create_role_name})`
                    )}
                  </td>
                  <td className="px-4 py-3">{rule.remove_when_lost ? "oui" : "non"}</td>
                  <td className="px-4 py-3 whitespace-nowrap">{rule.reconcile ? "Appliquée" : "Aperçu"}</td>
                  <td className="px-4 py-3">{rule.active ? "oui" : "non"}</td>
                  <td className="px-4 py-3">
                    <span className="flex flex-wrap gap-2">
                      <Button size="sm" variant="ghost" aria-controls={preview?.id === rule.id ? `${ids}-preview` : undefined} onClick={() => void showPreview(rule)}>
                        Voir l’aperçu
                      </Button>
                      <ConfirmButton
                        question={validateQuestion(rule)}
                        confirmLabel="Appliquer"
                        danger={false}
                        disabled={!seen}
                        onConfirm={() => validate(rule)}
                      >
                        Valider
                      </ConfirmButton>
                      <Button size="sm" variant="ghost" onClick={() => setForm({ kind: "edit", id: rule.id })}>
                        Modifier
                      </Button>
                      <ConfirmButton question={`Supprimer la règle « ${label(rule)} » ?`} confirmLabel="Supprimer" onConfirm={() => remove(rule)}>
                        Supprimer
                      </ConfirmButton>
                    </span>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {editing && (
        <RoleRuleForm
          key={editing.id}
          title={`Modifier la règle « ${label(editing)} »`}
          submitLabel="Enregistrer"
          initial={editing}
          roles={targetRoles}
          achievements={achievements}
          grades={grades}
          onSubmit={fields => update(editing, fields)}
          onCancel={() => setForm(null)}
        />
      )}

      {preview && previewed && (
        <section
          id={`${ids}-preview`}
          aria-labelledby={`${ids}-preview-title`}
          className="grid gap-4 rounded-[20px] border border-line bg-[rgb(19_22_42/0.92)] px-5 py-4"
        >
          <h2 id={`${ids}-preview-title`} className="m-0 font-display text-lg font-bold">
            Aperçu : {label(previewed)}
          </h2>
          {preview.status === "loading" && <p className="m-0 text-sm text-muted">Chargement de l’aperçu…</p>}
          {preview.status === "error" && (
            <p role="alert" className="m-0 text-sm text-orange">
              {preview.error}
            </p>
          )}
          {preview.status === "ok" && preview.data && (
            <PreviewBody
              data={preview.data}
              oldRole={oldRoleOf(previewed)}
              canMemberRoles={canMemberRoles}
              removeOld={removeOld}
              onRemoveOld={setRemoveOld}
              locked={preview.validated === true}
            />
          )}
          {preview.applyError && (
            <p role="alert" className="m-0 text-sm text-orange">
              {preview.applyError}
            </p>
          )}
          {preview.jobs && (
            <div className="grid gap-1">
              <JobProgress key={preview.jobs.apply} jobId={preview.jobs.apply} label="Application de la règle" />
              {preview.jobs.remove && (
                <JobProgress key={preview.jobs.remove} jobId={preview.jobs.remove} label="Retrait de l’ancien rôle" />
              )}
            </div>
          )}
        </section>
      )}
    </div>
  )
}

function NameList({ title, people, empty }: { title: string; people: RoleRulePreview["gain"]; empty: string }) {
  const listTitle = `${title} (${people.length})`
  if (people.length === 0) return <p className="m-0 text-sm text-muted">{empty}</p>
  return (
    <div className="grid content-start gap-2">
      <h3 className="m-0 text-sm font-semibold text-fg">{listTitle}</h3>
      <ul aria-label={listTitle} className="m-0 flex list-none flex-wrap gap-1.5 p-0">
        {people.slice(0, PREVIEW_NAMES).map(p => (
          <li key={p.id} className="rounded-full border border-line px-2.5 py-0.5 text-sm">
            {p.name}
          </li>
        ))}
      </ul>
      {people.length > PREVIEW_NAMES && (
        <p className="m-0 text-xs text-muted">et {plural(people.length - PREVIEW_NAMES, "autre")}.</p>
      )}
    </div>
  )
}

type BodyProps = {
  data: RoleRulePreview
  oldRole: OldRole | null
  canMemberRoles: boolean
  removeOld: boolean
  onRemoveOld: (v: boolean) => void
  locked: boolean
}

/** Qui gagne, qui perd ; retrait facultatif de l'ancien rôle (décoché par défaut). */
function PreviewBody({ data, oldRole, canMemberRoles, removeOld, onRemoveOld, locked }: BodyProps) {
  if (data.missing_role) {
    return (
      <p role="alert" className="m-0 text-sm text-orange">
        Le rôle de cette règle n’existe plus sur le serveur (rôle introuvable) : choisis un autre rôle avant de valider.
      </p>
    )
  }
  return (
    <div className="grid gap-4">
      <div className="grid gap-4 md:grid-cols-2">
        <NameList title="Gagnent le rôle" people={data.gain} empty="Personne ne gagne le rôle." />
        <NameList title="Perdent le rôle" people={data.lose} empty="Personne ne perd le rôle." />
      </div>
      {oldRole &&
        (canMemberRoles ? (
          <label className="flex items-start gap-2 text-sm text-msg">
            <input
              type="checkbox"
              checked={removeOld}
              disabled={locked}
              onChange={e => onRemoveOld(e.target.checked)}
              className="mt-0.5 size-4 accent-violet"
            />
            Retirer l’ancien rôle « {oldRole.name} » à ses {plural(oldRole.members, "membre")}
          </label>
        ) : (
          <p className="m-0 text-sm text-muted">
            L’ancien rôle « {oldRole.name} » reste en place : le retirer demande le droit « {PERMISSIONS["members.roles"]} ».
          </p>
        ))}
      <p className="m-0 text-xs text-muted">
        « Valider » applique la règle maintenant, puis la passe en mode « Appliquée » : Hermes la tient ensuite à jour pour tout le serveur.
      </p>
    </div>
  )
}
