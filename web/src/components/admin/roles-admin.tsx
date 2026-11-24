"use client"

import { Plus } from "lucide-react"
import { useId, useState } from "react"
import { Button } from "@/components/ui/button"
import { api } from "@/lib/api/client"
import type { ManagedRole, RoleInput, RolesOverview } from "@/lib/api/types"
import { cn } from "@/lib/cn"
import { plural } from "@/lib/jobs"
import { BulkRoles } from "./bulk-roles"
import { ConfirmButton } from "./confirm-button"
import { adminErrorText, FIELD, LABEL } from "./form"

/** Couleur Discord (entier) → `#rrggbb` ; 0 (pas de couleur) → noir, comme le sélecteur de Discord. */
export const colorHex = (color: number) => `#${color.toString(16).padStart(6, "0")}`
export const hexColor = (hex: string) => Number.parseInt(hex.replace("#", ""), 16) || 0
/** Pastille d'un rôle : gris neutre pour un rôle sans couleur. */
export const roleDot = (color: number) => (color ? colorHex(color) : "var(--color-muted)")

/** Pourquoi l'acteur ne peut pas gérer ce rôle ; `null` : gérable. Même ordre que les refus de web-api. */
function lockReason(role: ManagedRole, actor: RolesOverview["actor"]): string | null {
  if (role.managed) return "Géré par une intégration"
  if (!role.below_bot) return "Au-dessus du bot"
  if (role.editable) return null
  return role.position === actor.top_position ? "Votre rôle le plus haut" : "Au-dessus de vous"
}

type Props = {
  initial: RolesOverview
  /** Droit `roles.manage` : création, modification et suppression proposées. */
  canManage: boolean
  /** Droit `members.roles` : attribution en lot proposée. */
  canBulk: boolean
}

/** Rôles du serveur : création, modification, suppression (nombre de membres confirmé), lots. */
export function RolesAdmin({ initial, canManage, canBulk }: Props) {
  const [overview, setOverview] = useState(initial)
  const [creating, setCreating] = useState(false)
  const [editing, setEditing] = useState<ManagedRole | null>(null)
  const [success, setSuccess] = useState("")
  const [error, setError] = useState<string | null>(null)
  const createId = useId()

  /** Relit la liste (nombres de membres, positions) ; en cas d'échec, l'ancienne reste affichée. */
  async function reload() {
    try {
      setOverview(await api.admin.roles())
    } catch {
      /* liste conservée */
    }
  }

  function announce(text: string) {
    setError(null)
    setSuccess(text)
  }

  async function create(input: RoleInput): Promise<string | null> {
    try {
      await api.admin.createRole(input)
    } catch (e) {
      return adminErrorText(e)
    }
    setCreating(false)
    announce(`Rôle « ${input.name} » créé.`)
    await reload()
    return null
  }

  async function update(role: ManagedRole, input: RoleInput): Promise<string | null> {
    const changes: Partial<RoleInput> = {}
    if (input.name !== role.name) changes.name = input.name
    if (input.color !== role.color) changes.color = input.color
    if (Object.keys(changes).length === 0) return "Aucun changement à enregistrer."
    try {
      await api.admin.updateRole(role.id, changes)
    } catch (e) {
      return adminErrorText(e)
    }
    setEditing(null)
    announce(`Rôle « ${input.name} » enregistré.`)
    await reload()
    return null
  }

  async function remove(role: ManagedRole) {
    setSuccess("")
    setError(null)
    try {
      await api.admin.deleteRole(role.id, role.members)
      if (editing?.id === role.id) setEditing(null)
      announce(`Rôle « ${role.name} » supprimé.`)
    } catch (e) {
      setError(adminErrorText(e))
    }
    await reload() // 409 : le nombre a changé, la liste montre le nouveau
  }

  return (
    <div className="grid gap-6">
      <div className="flex flex-wrap items-center gap-3">
        {canManage && (
          <Button
            size="sm"
            aria-expanded={creating}
            aria-controls={creating ? createId : undefined}
            onClick={() => {
              setCreating(c => !c)
              setEditing(null)
            }}
          >
            <Plus aria-hidden="true" className="size-4" />
            Nouveau rôle
          </Button>
        )}
        <p role="status" aria-label="Rôles" className="m-0 text-sm text-green">
          {success}
        </p>
        {error && (
          <p role="alert" className="m-0 text-sm text-orange">
            {error}
          </p>
        )}
      </div>

      {canManage && creating && (
        <RoleForm
          id={createId}
          title="Nouveau rôle"
          submitLabel="Créer le rôle"
          initial={{ name: "", color: 0 }}
          onSubmit={create}
          onCancel={() => setCreating(false)}
        />
      )}

      <div className="overflow-x-auto rounded-[20px] border border-line">
        <table className="w-full border-collapse text-left text-sm">
          <caption className="sr-only">Rôles du serveur</caption>
          <thead className="text-muted">
            <tr>
              <th scope="col" className="px-4 py-3 font-semibold">Rôle</th>
              <th scope="col" className="px-4 py-3 font-semibold">Membres</th>
              {canManage && <th scope="col" className="px-4 py-3 font-semibold">Actions</th>}
            </tr>
          </thead>
          <tbody>
            {overview.roles.map(role => {
              const lock = lockReason(role, overview.actor)
              return (
                <tr key={role.id} className={cn("border-t border-line", lock && "text-muted")}>
                  <th scope="row" className="px-4 py-3 font-semibold">
                    <span className="flex items-center gap-2.5">
                      <span aria-hidden="true" className="size-3 flex-none rounded-full" style={{ background: roleDot(role.color) }} />
                      <span className={lock ? "text-muted" : "text-fg"}>{role.name}</span>
                    </span>
                  </th>
                  <td className="px-4 py-3 tabular-nums">{plural(role.members, "membre")}</td>
                  {canManage && <td className="px-4 py-3">
                    {lock ? (
                      <span className="text-muted">{lock}</span>
                    ) : (
                      <span className="flex flex-wrap gap-2">
                        <Button
                          size="sm"
                          variant="ghost"
                          aria-label={`Modifier « ${role.name} »`}
                          onClick={() => {
                            setEditing(role)
                            setCreating(false)
                          }}
                        >
                          Modifier
                        </Button>
                        <ConfirmButton
                          question={
                            role.members === 0
                              ? `Supprimer « ${role.name} » (aucun membre) ?`
                              : `Supprimer « ${role.name} » et le retirer à ${plural(role.members, "membre")} ?`
                          }
                          confirmLabel="Supprimer"
                          onConfirm={() => remove(role)}
                        >
                          Supprimer
                        </ConfirmButton>
                      </span>
                    )}
                  </td>}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {canManage && editing && (
        <RoleForm
          key={editing.id}
          title={`Modifier « ${editing.name} »`}
          submitLabel="Enregistrer"
          initial={{ name: editing.name, color: editing.color }}
          onSubmit={input => update(editing, input)}
          onCancel={() => setEditing(null)}
        />
      )}

      {canBulk && <BulkRoles roles={overview.roles} onDone={reload} />}
    </div>
  )
}

type FormProps = {
  id?: string
  title: string
  submitLabel: string
  initial: RoleInput
  /** Renvoie le message d'erreur à afficher, ou `null` en cas de succès. */
  onSubmit: (input: RoleInput) => Promise<string | null>
  onCancel: () => void
}

/** Nom (1 à 100 caractères) et couleur d'un rôle. */
function RoleForm({ id, title, submitLabel, initial, onSubmit, onCancel }: FormProps) {
  const ids = useId()
  const [name, setName] = useState(initial.name)
  const [color, setColor] = useState(colorHex(initial.color))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [nameInvalid, setNameInvalid] = useState(false)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    const trimmed = name.trim()
    if (!trimmed) {
      setNameInvalid(true)
      setError("Donne un nom au rôle.")
      return
    }
    setNameInvalid(false)
    setError(null)
    setBusy(true)
    const failure = await onSubmit({ name: trimmed, color: hexColor(color) })
    setBusy(false)
    if (failure) setError(failure)
  }

  return (
    <section id={id} aria-labelledby={`${ids}-title`} className="grid gap-4 rounded-[20px] border border-line bg-[rgb(19_22_42/0.92)] px-5 py-4">
      <h2 id={`${ids}-title`} className="m-0 font-display text-lg font-bold">
        {title}
      </h2>
      <form onSubmit={e => void submit(e)} className="grid gap-4 sm:grid-cols-[1fr_auto] sm:items-end">
        <div className="grid gap-1.5">
          <label htmlFor={`${ids}-name`} className={LABEL}>
            Nom du rôle
          </label>
          <input
            id={`${ids}-name`}
            className={FIELD}
            value={name}
            maxLength={100}
            aria-invalid={nameInvalid}
            onChange={e => setName(e.target.value)}
          />
        </div>
        <div className="grid gap-1.5">
          <label htmlFor={`${ids}-color`} className={LABEL}>
            Couleur
          </label>
          <input
            id={`${ids}-color`}
            type="color"
            className="h-11 w-20 cursor-pointer rounded-xl border border-white/14 bg-transparent p-1"
            value={color}
            onChange={e => setColor(e.target.value)}
          />
        </div>
        <div className="flex flex-wrap items-center gap-3 sm:col-span-2">
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
