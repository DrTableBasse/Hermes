"use client"

import { useId, useState } from "react"
import { Button } from "@/components/ui/button"
import { api, ApiError } from "@/lib/api/client"
import type { AccessOverview, AccessRole } from "@/lib/api/types"
import { cn } from "@/lib/cn"
import { PERMISSIONS, PERMISSION_GROUPS } from "@/lib/permissions"
import { adminErrorText } from "./form"

type Actor = AccessOverview["actor"]

type Props = {
  roles: AccessRole[]
  actor: Actor
  /** Rôle du réglage `admin_role` : tous les droits, calculés ; jamais proposé à la modification. */
  adminRoleId: string | null
}

/** Raison pour laquelle un rôle n'est pas modifiable ici ; `null` : modifiable. */
function lockReason(role: AccessRole, actor: Actor, adminRoleId: string | null): string | null {
  if (role.id === adminRoleId) return "Tous les droits (rôle administrateur)"
  if (role.managed) return "Rôle géré par une intégration (bot) : non modifiable"
  if (role.editable) return null
  return role.position === actor.top_position ? "Votre rôle le plus haut : non modifiable" : "Au-dessus de votre rôle"
}

const roleColor = (color: number) => (color ? `#${color.toString(16).padStart(6, "0")}` : "var(--color-muted)")
const sameSet = (a: readonly string[], b: readonly string[]) => [...a].sort().join() === [...b].sort().join()

/** Grille des accès : une carte par rôle (ordre Discord), droits groupés, enregistrement rôle par rôle. */
export function AccessGrid({ roles, actor, adminRoleId }: Props) {
  return (
    <ul className="m-0 grid list-none gap-4 p-0">
      {roles.map(role => (
        <li key={role.id}>
          <RoleAccess role={role} actor={actor} lock={lockReason(role, actor, adminRoleId)} />
        </li>
      ))}
    </ul>
  )
}

function RoleAccess({ role, actor, lock }: { role: AccessRole; actor: Actor; lock: string | null }) {
  const headingId = useId()
  const hintId = useId()
  const [saved, setSaved] = useState<string[]>(role.permissions)
  const [checked, setChecked] = useState<string[]>(role.permissions)
  const [saving, setSaving] = useState(false)
  const [success, setSuccess] = useState("")
  const [error, setError] = useState<string | null>(null)
  const owns = (key: string) => actor.is_owner || actor.permissions.includes(key)
  const dirty = !sameSet(checked, saved)

  function toggle(key: string) {
    setChecked(c => (c.includes(key) ? c.filter(k => k !== key) : [...c, key]))
    setSuccess("")
    setError(null)
  }

  async function save(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    setSuccess("")
    setError(null)
    try {
      const res = await api.admin.putAccess(role.id, [...checked].sort())
      setSaved(res.permissions)
      setChecked(res.permissions)
      setSuccess(`Accès de « ${role.name} » enregistrés : effet sous 10 minutes pour ses membres.`)
    } catch (err) {
      // 403 : le motif rédigé par l'API (position, droit que l'acteur n'a pas).
      setError(err instanceof ApiError && err.status === 403 ? err.message : adminErrorText(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <section
      aria-labelledby={headingId}
      className={cn(
        // Rôle verrouillé : grisé par la bordure et le fond, sans opacité (contraste du texte préservé).
        "grid gap-4 rounded-[20px] border px-5 py-4",
        lock ? "border-dashed border-line bg-transparent" : "border-line bg-[rgb(19_22_42/0.92)]",
      )}
    >
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span aria-hidden="true" className="size-3 flex-none rounded-full" style={{ background: roleColor(role.color) }} />
        <h2 id={headingId} className="m-0 font-display text-lg font-bold">
          {role.name}
        </h2>
        {lock && <p className="m-0 text-sm text-muted">{lock}</p>}
      </div>

      {!lock && (
        <form onSubmit={e => void save(e)} className="grid gap-4">
          <p id={hintId} className="m-0 text-xs text-muted">
            {actor.is_owner
              ? "Propriétaire du serveur : tous les droits sont modifiables."
              : "Cases grisées : droits que vous n’avez pas vous-même, donc ni accordables ni retirables."}
          </p>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {PERMISSION_GROUPS.map(group => (
              <fieldset key={group.label} className="m-0 grid content-start gap-2 border-0 p-0">
                <legend className="mb-1 p-0 text-sm font-semibold text-fg">{group.label}</legend>
                {group.permissions.map(key => {
                  const disabled = !owns(key) || saving
                  return (
                    <label
                      key={key}
                      className={cn("flex items-start gap-2 text-sm", owns(key) ? "text-msg" : "text-muted")}
                    >
                      <input
                        type="checkbox"
                        checked={checked.includes(key)}
                        disabled={disabled}
                        aria-describedby={owns(key) ? undefined : hintId}
                        onChange={() => toggle(key)}
                        className="mt-0.5 size-4 flex-none accent-violet"
                      />
                      <span>{PERMISSIONS[key]}</span>
                    </label>
                  )
                })}
              </fieldset>
            ))}
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Button type="submit" size="sm" disabled={!dirty || saving}>
              {saving ? "Enregistrement…" : "Enregistrer"}
            </Button>
            <p role="status" className="m-0 text-sm text-green">
              {success}
            </p>
            {error && (
              <p role="alert" className="m-0 text-sm text-orange">
                {error}
              </p>
            )}
          </div>
        </form>
      )}
    </section>
  )
}
