"use client"

import { useEffect, useId, useRef, useState } from "react"
import { Button, buttonVariants } from "@/components/ui/button"
import { api } from "@/lib/api/client"
import type { DiscordPermissionRole, DiscordPermissionsOverview } from "@/lib/api/types"
import { cn } from "@/lib/cn"
import { PERMISSION_FAMILIES } from "@/lib/discord-permissions"
import { botActionErrorText, FIELD, LABEL } from "./form"

type Actor = DiscordPermissionsOverview["actor"]

const ADMINISTRATOR = "administrator"
const ORDER = PERMISSION_FAMILIES.flatMap(f => f.permissions.map(p => p.key))
const LABELS: Record<string, string> = Object.fromEntries(
  PERMISSION_FAMILIES.flatMap(f => f.permissions.map(p => [p.key, p.label])),
)
const inOrder = (keys: Iterable<string>) => {
  const set = new Set(keys)
  return ORDER.filter(k => set.has(k))
}

/** Raison courte pour un rôle non modifiable (liste des rôles, en-tête de la grille). */
function roleLockLabel(role: DiscordPermissionRole, actor: Actor): string | null {
  if (role.editable) return null
  if (role.is_default) return "réservé au propriétaire"
  if (role.managed) return "rôle d’intégration"
  if (!actor.is_owner && role.position >= actor.top_position) return "rôle au-dessus du vôtre"
  return "rôle au-dessus d’Hermes"
}

/** Raison pour laquelle l'acteur ne peut pas basculer ce drapeau sur un rôle modifiable ; `null` : il peut. */
function flagLockLabel(role: DiscordPermissionRole, key: string, actor: Actor): string | null {
  if (role.editable_flags.includes(key)) return null
  if (key === ADMINISTRATOR && !actor.is_owner && !role.permissions.includes(key)) return "réservé au propriétaire"
  return "vous n’avez pas cette permission"
}

type Stage = "edit" | "confirm-admin" | "review"

/** Grille des permissions Discord d'un rôle choisi : familles, récapitulatif avant/après, confirmation. */
export function DiscordPermissionsGrid({ initial }: { initial: DiscordPermissionsOverview }) {
  const { actor } = initial
  const selectId = useId()
  const [roles, setRoles] = useState(initial.roles)
  const firstEditable = initial.roles.find(r => r.editable) ?? initial.roles[0]
  const [roleId, setRoleId] = useState(firstEditable?.id ?? "")
  const role = roles.find(r => r.id === roleId)
  const [checked, setChecked] = useState<string[]>(role?.permissions ?? [])
  const [adminConfirmed, setAdminConfirmed] = useState(false)
  const [stage, setStage] = useState<Stage>("edit")
  const [saving, setSaving] = useState(false)
  const [success, setSuccess] = useState("")
  const [error, setError] = useState<string | null>(null)

  if (!role) return <p className="m-0 text-muted">Aucun rôle sur le serveur.</p>

  const before = new Set(role.permissions)
  const after = new Set(checked)
  const added = inOrder(checked.filter(k => !before.has(k)))
  const removed = inOrder(role.permissions.filter(k => !after.has(k)))
  const dirty = added.length > 0 || removed.length > 0

  function reset(next: DiscordPermissionRole) {
    setChecked(next.permissions)
    setAdminConfirmed(false)
    setStage("edit")
  }

  function chooseRole(id: string) {
    const next = roles.find(r => r.id === id)
    if (!next) return
    setRoleId(id)
    reset(next)
    setSuccess("")
    setError(null)
  }

  function toggle(key: string) {
    setSuccess("")
    setError(null)
    if (checked.includes(key)) {
      setChecked(c => c.filter(k => k !== key))
      if (key === ADMINISTRATOR) setAdminConfirmed(false)
    } else if (key === ADMINISTRATOR && !before.has(key)) {
      setStage("confirm-admin")
    } else {
      setChecked(c => [...c, key])
    }
  }

  async function save() {
    if (!role) return
    setSaving(true)
    setError(null)
    try {
      const res = await api.admin.putRolePermissions(
        role.id,
        inOrder(checked),
        adminConfirmed && checked.includes(ADMINISTRATOR),
      )
      setRoles(rs => rs.map(r => (r.id === res.role.id ? res.role : r)))
      reset(res.role)
      setSuccess(
        res.changed ? `Permissions de « ${res.role.name} » enregistrées sur Discord.` : "Aucun changement : rien n’a été envoyé.",
      )
    } catch (err) {
      setStage("edit")
      setError(botActionErrorText(err))
    } finally {
      setSaving(false)
    }
  }

  const roleLock = roleLockLabel(role, actor)
  const locked = stage !== "edit" || saving

  return (
    <section aria-labelledby={`${selectId}-h`} className="grid gap-5">
      <h2 id={`${selectId}-h`} className="m-0 font-display text-xl font-bold">
        Permissions Discord
      </h2>
      <div className="grid max-w-md gap-1.5">
        <label htmlFor={selectId} className={LABEL}>
          Rôle
        </label>
        <select
          id={selectId}
          value={role.id}
          disabled={locked}
          onChange={e => chooseRole(e.target.value)}
          className={FIELD}
        >
          {roles.map(r => {
            const lock = roleLockLabel(r, actor)
            return (
              <option key={r.id} value={r.id}>
                {r.name}
                {lock ? ` — ${lock}` : ""}
              </option>
            )
          })}
        </select>
      </div>

      {roleLock ? (
        <p id={`${selectId}-lock`} className="m-0 rounded-2xl border border-dashed border-line px-5 py-4 text-sm text-muted">
          Non modifiable ({roleLock}) : {role.refusal ?? "vous ne pouvez pas modifier ce rôle"}.
        </p>
      ) : (
        <p className="m-0 text-xs text-muted">
          {actor.is_owner
            ? "Propriétaire du serveur : toutes les permissions sont modifiables ; « Administrateur » demande une confirmation."
            : "Cases désactivées : permissions que vous n’avez pas vous-même, donc ni accordables ni retirables."}
        </p>
      )}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {PERMISSION_FAMILIES.map(family => (
          <fieldset key={family.family} className="m-0 grid content-start gap-2 border-0 p-0">
            <legend className="mb-1 p-0 text-sm font-semibold text-fg">{family.family}</legend>
            {family.permissions.map(({ key, label }) => {
              const flagLock = roleLock ? null : flagLockLabel(role, key, actor)
              const canToggle = !roleLock && !flagLock
              return (
                <label key={key} className={cn("flex items-start gap-2 text-sm", canToggle ? "text-msg" : "text-muted")}>
                  <input
                    type="checkbox"
                    checked={checked.includes(key)}
                    disabled={!canToggle || locked}
                    aria-describedby={roleLock ? `${selectId}-lock` : undefined}
                    onChange={() => toggle(key)}
                    className="mt-0.5 size-4 flex-none accent-violet"
                  />
                  <span>
                    {label}
                    {flagLock && " "}
                    {flagLock && <span className="text-xs">({flagLock})</span>}
                  </span>
                </label>
              )
            })}
          </fieldset>
        ))}
      </div>

      {stage === "confirm-admin" && (
        <ConfirmPanel
          title="Accorder « Administrateur » ?"
          confirmLabel="Accorder Administrateur"
          onConfirm={() => {
            setChecked(c => [...c, ADMINISTRATOR])
            setAdminConfirmed(true)
            setStage("edit")
          }}
          onCancel={() => setStage("edit")}
        >
          <p className="m-0 text-sm text-fg">
            Les membres de « {role.name} » auront toutes les permissions du serveur, quels que soient les réglages des
            salons.
          </p>
        </ConfirmPanel>
      )}

      {stage === "review" && (
        <ConfirmPanel
          title={`Récapitulatif pour « ${role.name} »`}
          confirmLabel={saving ? "Enregistrement…" : "Confirmer l’enregistrement"}
          busy={saving}
          onConfirm={() => void save()}
          onCancel={() => setStage("edit")}
        >
          <Changes title="Permissions ajoutées" keys={added} />
          <Changes title="Permissions retirées" keys={removed} />
        </ConfirmPanel>
      )}

      {!roleLock && stage === "edit" && (
        <div className="flex flex-wrap items-center gap-3">
          <Button type="button" size="sm" disabled={!dirty || saving} onClick={() => setStage("review")}>
            Enregistrer
          </Button>
          {dirty && (
            <button type="button" onClick={() => reset(role)} className={buttonVariants({ variant: "ghost", size: "sm" })}>
              Annuler les changements
            </button>
          )}
        </div>
      )}
      <p role="status" className="m-0 text-sm text-green">
        {success}
      </p>
      {error && (
        <p role="alert" className="m-0 text-sm text-orange">
          {error}
        </p>
      )}
    </section>
  )
}

function Changes({ title, keys }: { title: string; keys: string[] }) {
  return (
    <div className="grid gap-1">
      <p className="m-0 text-sm font-semibold text-fg">{title}</p>
      {keys.length ? (
        <ul className="m-0 grid gap-0.5 pl-5 text-sm text-msg">
          {keys.map(k => (
            <li key={k}>{LABELS[k] ?? k}</li>
          ))}
        </ul>
      ) : (
        <p className="m-0 text-sm text-muted">Aucune</p>
      )}
    </div>
  )
}

/** Panneau de confirmation dans la page : focus sur « Annuler » à l'ouverture, Échap referme. */
function ConfirmPanel({
  title,
  confirmLabel,
  busy = false,
  onConfirm,
  onCancel,
  children,
}: {
  title: string
  confirmLabel: string
  busy?: boolean
  onConfirm: () => void
  onCancel: () => void
  children: React.ReactNode
}) {
  const titleId = useId()
  const cancel = useRef<HTMLButtonElement>(null)
  useEffect(() => cancel.current?.focus(), [])
  return (
    <div
      role="group"
      aria-labelledby={titleId}
      onKeyDown={e => {
        if (e.key === "Escape" && !busy) onCancel()
      }}
      className="grid gap-3 rounded-2xl border border-orange/40 bg-orange/8 px-5 py-4"
    >
      <p id={titleId} className="m-0 font-semibold text-fg">
        {title}
      </p>
      {children}
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          disabled={busy}
          onClick={onConfirm}
          className="rounded-[10px] bg-orange px-3 py-[5px] text-[13px] font-bold text-[#1a0c02] disabled:opacity-60"
        >
          {confirmLabel}
        </button>
        <button
          ref={cancel}
          type="button"
          disabled={busy}
          onClick={onCancel}
          className={buttonVariants({ variant: "ghost", size: "sm" })}
        >
          Annuler
        </button>
      </div>
    </div>
  )
}
