"use client"

import { useState } from "react"
import { api } from "@/lib/api/client"
import { cn } from "@/lib/cn"
import { adminErrorText } from "./form"

type Props = {
  commands: Record<string, boolean>
  descriptions: Record<string, string>
}

/** Interrupteurs des commandes slash (`POST /admin/commands/toggle`) ; l'état ne change qu'après réponse. */
export function CommandsPanel({ commands: initial, descriptions }: Props) {
  const [commands, setCommands] = useState(initial)
  const [pending, setPending] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const names = Object.keys(commands).sort((a, b) => a.localeCompare(b, "fr"))

  async function toggle(name: string) {
    const next = !commands[name]
    setPending(name)
    setError(null)
    try {
      await api.admin.toggleCommand({ command_name: name, enabled: next })
      setCommands(c => ({ ...c, [name]: next }))
    } catch (e) {
      setError(`/${name} : ${adminErrorText(e)}`)
    } finally {
      setPending(null)
    }
  }

  return (
    <div className="grid gap-4">
      <p role="alert" className={cn("m-0 text-sm text-orange", !error && "sr-only")}>
        {error}
      </p>
      <ul className="m-0 grid list-none gap-3 p-0 sm:grid-cols-2 lg:grid-cols-3">
        {names.map(name => {
          const enabled = commands[name]
          return (
            <li
              key={name}
              className="flex items-start justify-between gap-3 rounded-2xl border border-line bg-[rgb(19_22_42/0.92)] px-4 py-3"
            >
              <div className="min-w-0">
                <p className="m-0 font-mono text-sm font-semibold">/{name}</p>
                <p className="m-0 mt-0.5 text-xs text-muted">{descriptions[name] || "Pas de description."}</p>
              </div>
              <button
                type="button"
                role="switch"
                aria-checked={enabled}
                aria-label={`/${name}`}
                disabled={pending !== null}
                onClick={() => void toggle(name)}
                className={cn(
                  "relative mt-0.5 inline-flex h-6 w-11 flex-none items-center rounded-full transition-colors disabled:opacity-60",
                  enabled ? "bg-green/80" : "bg-white/14",
                )}
              >
                <span
                  aria-hidden="true"
                  className={cn("inline-block size-4 rounded-full bg-white transition-transform", enabled ? "translate-x-6" : "translate-x-1")}
                />
              </button>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
