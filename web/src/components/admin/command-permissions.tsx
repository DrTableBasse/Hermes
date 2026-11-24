"use client"

import { useId, useState } from "react"
import { Button, buttonVariants } from "@/components/ui/button"
import { api } from "@/lib/api/client"
import type { CommandPermission, CommandPermissionsOverview } from "@/lib/api/types"
import { botActionErrorText, FIELD } from "./form"

type ServerRole = CommandPermissionsOverview["roles"][number]
type Entry = { id: string; name: string; deleted: boolean }

const RELOAD_FAILED_TEXT =
  "Enregistré, mais le bot ne l’a pas encore pris en compte : réessayez ou redémarrez le bot."

/** Effet d'une liste blanche (le propriétaire et le rôle administrateur passent toujours). */
function effectText(adminOnly: boolean, entries: Entry[]): string {
  if (!entries.length) return adminOnly ? "Administrateurs seulement" : "Tout le monde"
  const names = entries.map(e => e.name).join(", ")
  return adminOnly ? `Administrateurs et : ${names}` : `Seulement : ${names} (et les administrateurs)`
}

/** Listes blanches des commandes Hermes, groupées « réservées aux admins » / « ouvertes ». */
export function CommandPermissions({ initial }: { initial: CommandPermissionsOverview }) {
  const admin = initial.commands.filter(c => c.admin_only)
  const open = initial.commands.filter(c => !c.admin_only)
  return (
    <div className="grid gap-8">
      <CommandGroup
        title="Réservées aux admins"
        hint="Liste vide : administrateurs seulement. Un rôle ajouté peut aussi les utiliser."
        commands={admin}
        roles={initial.roles}
      />
      <CommandGroup
        title="Ouvertes"
        hint="Liste vide : tout le monde. Une liste non vide limite la commande à ces rôles."
        commands={open}
        roles={initial.roles}
      />
    </div>
  )
}

function CommandGroup({
  title,
  hint,
  commands,
  roles,
}: {
  title: string
  hint: string
  commands: CommandPermission[]
  roles: ServerRole[]
}) {
  const headingId = useId()
  return (
    <section aria-labelledby={headingId} className="grid gap-3">
      <h2 id={headingId} className="m-0 font-display text-xl font-bold">
        {title}
      </h2>
      <p className="m-0 text-sm text-muted">{hint}</p>
      {commands.length ? (
        <ul className="m-0 grid list-none gap-3 p-0">
          {commands.map(c => (
            <li key={c.name}>
              <CommandRow command={c} roles={roles} />
            </li>
          ))}
        </ul>
      ) : (
        <p className="m-0 text-sm text-muted">Aucune commande.</p>
      )}
    </section>
  )
}

function CommandRow({ command, roles }: { command: CommandPermission; roles: ServerRole[] }) {
  const headingId = useId()
  const selectId = useId()
  const byId = new Map(roles.map(r => [r.id, r]))
  const initialEntries: Entry[] = command.roles.map(r => ({
    id: r.id,
    name: r.deleted || !r.name ? `Rôle supprimé (${r.id})` : r.name,
    deleted: r.deleted,
  }))
  const [saved, setSaved] = useState<Entry[]>(initialEntries)
  const [draft, setDraft] = useState<Entry[]>(initialEntries)
  const [pick, setPick] = useState("")
  const [saving, setSaving] = useState(false)
  const [success, setSuccess] = useState("")
  const [warning, setWarning] = useState("")
  const [error, setError] = useState<string | null>(null)

  const dirty = saved.map(e => e.id).join() !== draft.map(e => e.id).join()
  const candidates = roles.filter(r => r.assignable && !draft.some(e => e.id === r.id))
  const restrict = !command.admin_only && draft.length === 0

  function clearFeedback() {
    setSuccess("")
    setWarning("")
    setError(null)
  }

  function add() {
    const role = byId.get(pick)
    if (!role) return
    setDraft(d => [...d, { id: role.id, name: role.name, deleted: false }])
    setPick("")
    clearFeedback()
  }

  function remove(id: string) {
    setDraft(d => d.filter(e => e.id !== id))
    clearFeedback()
  }

  async function save() {
    setSaving(true)
    clearFeedback()
    try {
      const res = await api.admin.putCommandPermissions(command.name, draft.map(e => e.id))
      const kept = res.role_ids.map(id => draft.find(e => e.id === id) ?? { id, name: byId.get(id)?.name ?? id, deleted: false })
      setSaved(kept)
      setDraft(kept)
      if (res.reload_failed) setWarning(RELOAD_FAILED_TEXT)
      else setSuccess(res.changed ? `/${command.name} : ${effectText(command.admin_only, kept)}.` : "Aucun changement.")
    } catch (err) {
      setError(botActionErrorText(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <section aria-labelledby={headingId} className="grid gap-3 rounded-[20px] border border-line bg-[rgb(19_22_42/0.92)] px-5 py-4">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h3 id={headingId} className="m-0 font-mono text-base font-bold">
          /{command.name}
        </h3>
        {command.description && <p className="m-0 text-sm text-muted">{command.description}</p>}
      </div>
      <p className="m-0 text-sm text-fg">
        Accès : <strong>{effectText(command.admin_only, draft)}</strong>
      </p>
      {command.native_protected && (
        <p className="m-0 text-xs text-muted">Protégée aussi par une permission Discord : elle s’applique en plus de cette liste.</p>
      )}

      {draft.length > 0 && (
        <ul aria-label={`Rôles autorisés pour /${command.name}`} className="m-0 flex list-none flex-wrap gap-2 p-0">
          {draft.map(e => {
            const role = byId.get(e.id)
            // Un rôle supprimé de Discord se retire toujours (nettoyage).
            const removable = command.editable && (e.deleted || !role || role.assignable)
            return (
              <li key={e.id} className="inline-flex items-center gap-2 rounded-full border border-line px-3 py-1 text-sm">
                <span className={e.deleted ? "text-orange" : "text-msg"}>{e.name}</span>
                {removable ? (
                  <button
                    type="button"
                    disabled={saving}
                    onClick={() => remove(e.id)}
                    aria-label={`Retirer ${e.name}`}
                    className="text-muted hover:text-fg"
                  >
                    ✕
                  </button>
                ) : (
                  command.editable && <span className="text-xs text-muted">(rôle au-dessus du vôtre)</span>
                )}
              </li>
            )
          })}
        </ul>
      )}

      {!command.editable ? (
        <p className="m-0 text-xs text-muted">Réservée aux administrateurs du site : seuls eux peuvent l’ouvrir à d’autres rôles.</p>
      ) : (
        <div className="flex flex-wrap items-center gap-2">
          <label htmlFor={selectId} className="sr-only">
            Rôle à autoriser pour /{command.name}
          </label>
          <select
            id={selectId}
            value={pick}
            disabled={saving || candidates.length === 0}
            onChange={e => setPick(e.target.value)}
            className={`${FIELD} w-auto min-w-48`}
          >
            <option value="">{candidates.length ? "Choisir un rôle…" : "Aucun rôle sous le vôtre"}</option>
            {candidates.map(r => (
              <option key={r.id} value={r.id}>
                {r.name}
              </option>
            ))}
          </select>
          <button
            type="button"
            disabled={!pick || saving}
            onClick={add}
            className={buttonVariants({ variant: "ghost", size: "sm" })}
          >
            {restrict ? "Restreindre à ce rôle" : "Ajouter"}
          </button>
          {dirty && (
            <>
              <Button type="button" size="sm" disabled={saving} onClick={() => void save()}>
                {saving ? "Enregistrement…" : "Enregistrer"}
              </Button>
              <button
                type="button"
                disabled={saving}
                onClick={() => {
                  setDraft(saved)
                  clearFeedback()
                }}
                className={buttonVariants({ variant: "ghost", size: "sm" })}
              >
                Annuler
              </button>
            </>
          )}
        </div>
      )}
      {dirty && !command.admin_only && draft.length === 0 && (
        <p className="m-0 text-xs text-muted">Après enregistrement, la commande sera de nouveau ouverte à tout le monde.</p>
      )}
      <p role="status" className="m-0 text-sm text-green">
        {success}
      </p>
      {warning && (
        <p role="alert" className="m-0 text-sm text-orange">
          {warning}
        </p>
      )}
      {error && (
        <p role="alert" className="m-0 text-sm text-orange">
          {error}
        </p>
      )}
    </section>
  )
}
