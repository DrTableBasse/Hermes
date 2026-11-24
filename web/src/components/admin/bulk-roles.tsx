"use client"

import { X } from "lucide-react"
import { useId, useState } from "react"
import { api } from "@/lib/api/client"
import type { BulkRolesInput, ManagedRole, UserSearchResult } from "@/lib/api/types"
import { plural } from "@/lib/jobs"
import { ConfirmButton } from "./confirm-button"
import { adminErrorText, FIELD, LABEL } from "./form"
import { JobProgress } from "./job-progress"
import { UserSearchInput } from "./user-search-input"

type Props = {
  roles: ManagedRole[]
  /** Appelé quand un lot ne tourne plus : les nombres de membres ont changé. */
  onDone: () => void
}

const RADIO = "flex items-center gap-2 text-sm text-msg"

/**
 * Attribution ou retrait d'un rôle en lot, à des membres choisis ou aux porteurs d'un autre rôle :
 * nombre annoncé et confirmé (web-api refuse un nombre périmé), puis suivi du travail du bot.
 */
export function BulkRoles({ roles, onDone }: Props) {
  const ids = useId()
  const manageable = roles.filter(r => r.editable)
  const [roleId, setRoleId] = useState(manageable[0]?.id ?? "")
  const [action, setAction] = useState<"add" | "remove">("add")
  const [source, setSource] = useState<"members" | "role">("members")
  const [members, setMembers] = useState<UserSearchResult[]>([])
  const [fromRoleId, setFromRoleId] = useState("")
  const [searchKey, setSearchKey] = useState(0)
  const [jobId, setJobId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const target = manageable.find(r => r.id === roleId)
  const from = roles.find(r => r.id === fromRoleId)
  const count = source === "members" ? members.length : (from?.members ?? 0)

  function addMember(user: UserSearchResult) {
    setMembers(list => (list.some(m => m.user_id === user.user_id) ? list : [...list, user]))
    setSearchKey(k => k + 1) // champ de recherche vidé pour le membre suivant
  }

  async function run() {
    if (!target) return
    setError(null)
    setJobId(null)
    const body: BulkRolesInput =
      source === "members"
        ? { action, user_ids: members.map(m => m.user_id), confirm_count: count }
        : { action, from_role_id: fromRoleId, confirm_count: count }
    try {
      setJobId((await api.admin.bulkRoles(target.id, body)).job_id)
    } catch (e) {
      setError(adminErrorText(e))
    }
  }

  return (
    <section aria-labelledby={`${ids}-title`} className="grid gap-4 rounded-[20px] border border-line bg-[rgb(19_22_42/0.92)] px-5 py-4">
      <h2 id={`${ids}-title`} className="m-0 font-display text-lg font-bold">
        Attribuer en lot
      </h2>
      {manageable.length === 0 ? (
        <p className="m-0 text-sm text-muted">Aucun rôle sous le vôtre ni sous celui d’Hermes : rien à attribuer.</p>
      ) : (
        <div className="grid gap-4">
          <div className="grid gap-4 md:grid-cols-3">
            <div className="grid content-start gap-1.5">
              <label htmlFor={`${ids}-role`} className={LABEL}>
                Rôle
              </label>
              <select id={`${ids}-role`} className={FIELD} value={roleId} onChange={e => setRoleId(e.target.value)}>
                {manageable.map(r => (
                  <option key={r.id} value={r.id}>
                    {r.name}
                  </option>
                ))}
              </select>
            </div>
            <fieldset className="m-0 grid content-start gap-2 border-0 p-0">
              <legend className={`${LABEL} mb-1.5 p-0`}>Action</legend>
              <label className={RADIO}>
                <input type="radio" name={`${ids}-action`} checked={action === "add"} onChange={() => setAction("add")} className="accent-violet" />
                Ajouter
              </label>
              <label className={RADIO}>
                <input type="radio" name={`${ids}-action`} checked={action === "remove"} onChange={() => setAction("remove")} className="accent-violet" />
                Retirer
              </label>
            </fieldset>
            <fieldset className="m-0 grid content-start gap-2 border-0 p-0">
              <legend className={`${LABEL} mb-1.5 p-0`}>Membres visés</legend>
              <label className={RADIO}>
                <input type="radio" name={`${ids}-source`} checked={source === "members"} onChange={() => setSource("members")} className="accent-violet" />
                Membres choisis
              </label>
              <label className={RADIO}>
                <input type="radio" name={`${ids}-source`} checked={source === "role"} onChange={() => setSource("role")} className="accent-violet" />
                Tous ceux qui ont le rôle
              </label>
            </fieldset>
          </div>

          {source === "members" ? (
            <div className="grid gap-3">
              <div className="max-w-sm">
                <UserSearchInput key={searchKey} label="Ajouter un membre" selected={null} onSelect={addMember} onClear={() => {}} />
              </div>
              {members.length > 0 && (
                <ul aria-label="Membres choisis" className="m-0 flex list-none flex-wrap gap-2 p-0">
                  {members.map(m => (
                    <li key={m.user_id} className="flex items-center gap-1.5 rounded-full border border-line py-1 pr-1.5 pl-3 text-sm">
                      {m.username}
                      <button
                        type="button"
                        aria-label={`Retirer ${m.username} de la liste`}
                        onClick={() => setMembers(list => list.filter(x => x.user_id !== m.user_id))}
                        className="grid size-6 place-items-center rounded-full text-muted hover:bg-white/10 hover:text-fg"
                      >
                        <X aria-hidden="true" className="size-3.5" />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ) : (
            <div className="grid max-w-sm gap-1.5">
              <label htmlFor={`${ids}-from`} className={LABEL}>
                Rôle source
              </label>
              <select id={`${ids}-from`} className={FIELD} value={fromRoleId} onChange={e => setFromRoleId(e.target.value)}>
                <option value="">Choisir un rôle</option>
                {roles.map(r => (
                  <option key={r.id} value={r.id}>
                    {r.name}
                  </option>
                ))}
              </select>
            </div>
          )}

          <div className="flex flex-wrap items-center gap-3">
            <p className="m-0 text-sm font-semibold text-fg">
              {plural(count, "membre")} concerné{count > 1 ? "s" : ""}
            </p>
            {source === "role" && (
              <p className="m-0 text-xs text-muted">(le nombre peut inclure quelques bots, qu’Hermes ignore)</p>
            )}
            <ConfirmButton
              question={`${action === "add" ? "Ajouter" : "Retirer"} « ${target?.name ?? ""} » à ${plural(count, "membre")} ?`}
              confirmLabel="Confirmer"
              danger={action === "remove"}
              disabled={count === 0 || !target}
              onConfirm={run}
            >
              Confirmer
            </ConfirmButton>
          </div>
          {error && (
            <p role="alert" className="m-0 text-sm text-orange">
              {error}
            </p>
          )}
          {jobId && <JobProgress key={jobId} jobId={jobId} label="Suivi du lot" onSettled={onDone} />}
        </div>
      )}
    </section>
  )
}
