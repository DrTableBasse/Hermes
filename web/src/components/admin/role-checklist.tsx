"use client"

import type { DiscordRole } from "@/lib/api/types"
import { splitIds } from "./key-settings"

type Props = {
  id: string
  /** Élément qui nomme le groupe (libellé du réglage). */
  labelledBy: string
  describedBy?: string
  /** Identifiants séparés par des virgules, dans l'ordre enregistré. */
  value: string
  roles: DiscordRole[]
  onChange: (value: string) => void
}

/** Sélection multiple de rôles : une case par rôle ; un identifiant inconnu de Discord reste décochable. */
export function RoleChecklist({ id, labelledBy, describedBy, value, roles, onChange }: Props) {
  const selected = splitIds(value)
  const unknown = selected.filter(r => !roles.some(x => x.id === r))
  const toggle = (roleId: string, on: boolean) =>
    onChange((on ? [...selected, roleId] : selected.filter(r => r !== roleId)).join(","))
  const options = [...unknown.map(r => ({ id: r, name: `Introuvable (${r})` })), ...roles.map(r => ({ id: r.id, name: `@${r.name}` }))]

  return (
    <div
      id={id}
      role="group"
      aria-labelledby={labelledBy}
      aria-describedby={describedBy}
      className="grid max-h-56 w-full max-w-md gap-1 overflow-y-auto rounded-xl border border-white/14 bg-[rgb(12_14_26/0.6)] p-2"
    >
      {options.map(o => (
        <label key={o.id} className="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 text-sm hover:bg-white/6">
          <input
            type="checkbox"
            checked={selected.includes(o.id)}
            onChange={e => toggle(o.id, e.target.checked)}
            className="size-4 accent-violet"
          />
          <span className={o.name.startsWith("Introuvable") ? "text-orange" : undefined}>{o.name}</span>
        </label>
      ))}
    </div>
  )
}
