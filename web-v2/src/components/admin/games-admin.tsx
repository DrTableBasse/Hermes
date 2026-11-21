"use client"

import { ArrowDown, ArrowUp } from "lucide-react"
import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Chip } from "@/components/ui/chip"
import { Panel } from "@/components/ui/panel"
import { api } from "@/lib/api/client"
import type { AdminGame, DiscordChannel, DiscordRole } from "@/lib/api/types"
import { cn } from "@/lib/cn"
import { adminErrorText, type Feedback } from "./form"
import { GameForm, type GameDraft } from "./game-form"

type Props = { games: AdminGame[]; roles: DiscordRole[] | null; channels: DiscordChannel[] | null }

const byPosition = (a: AdminGame, b: AdminGame) => a.position - b.position || a.key.localeCompare(b.key)

const fields = (d: GameDraft) => ({
  name: d.name,
  color: d.color,
  image: d.image,
  tagline: d.tagline,
  discord_role_id: d.discord_role_id,
  forum_channel_id: d.forum_channel_id,
  position: d.position,
})

/** Jeux de la communauté : ajout, édition, ordre, désactivation (les jeux inactifs restent listés). */
export function GamesAdmin({ games: initial, roles, channels }: Props) {
  const [games, setGames] = useState([...initial].sort(byPosition))
  const [open, setOpen] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [feedback, setFeedback] = useState<Feedback>(null)

  async function run(action: () => Promise<void>, done: string) {
    setBusy(true)
    setFeedback(null)
    try {
      await action()
      setFeedback({ kind: "ok", text: done })
    } catch (e) {
      setFeedback({ kind: "error", text: adminErrorText(e) })
    } finally {
      setBusy(false)
    }
  }

  const create = (d: GameDraft) =>
    run(async () => {
      await api.admin.createGame({ key: d.key, ...fields(d) })
      setGames(list => [...list, { ...d, active: true }].sort(byPosition))
      setOpen(null)
    }, `« ${d.name} » ajouté.`)

  const update = (key: string, d: GameDraft) =>
    run(async () => {
      await api.admin.updateGame(key, fields(d))
      setGames(list => list.map(g => (g.key === key ? { ...g, ...d, key } : g)).sort(byPosition))
      setOpen(null)
    }, `« ${d.name} » enregistré.`)

  const setActive = (g: AdminGame, active: boolean) =>
    run(async () => {
      if (active) await api.admin.updateGame(g.key, { active: true })
      else await api.admin.deactivateGame(g.key)
      setGames(list => list.map(x => (x.key === g.key ? { ...x, active } : x)))
    }, active ? `« ${g.name} » réactivé.` : `« ${g.name} » désactivé : il disparaît du site.`)

  /** Échange avec le voisin puis renumérote 1…n ; seules les positions modifiées sont envoyées. */
  const move = (index: number, delta: -1 | 1) =>
    run(async () => {
      const next = [...games]
      ;[next[index], next[index + delta]] = [next[index + delta], next[index]]
      const renumbered = next.map((g, i) => ({ ...g, position: i + 1 }))
      for (const g of renumbered) {
        if (games.find(x => x.key === g.key)?.position !== g.position) await api.admin.updateGame(g.key, { position: g.position })
      }
      setGames(renumbered)
    }, "Ordre enregistré.")

  const nextPosition = games.reduce((m, g) => Math.max(m, g.position), 0) + 1
  const blank: GameDraft = { key: "", name: "", color: "#9B6BFF", image: null, tagline: null, discord_role_id: null, forum_channel_id: null, position: nextPosition }

  return (
    <div className="grid gap-6">
      <div className="flex flex-wrap items-center gap-3">
        <Button size="sm" disabled={busy} onClick={() => setOpen(open === "new" ? null : "new")}>
          Ajouter un jeu
        </Button>
        {feedback && (
          <p role={feedback.kind === "error" ? "alert" : "status"} className={cn("m-0 text-sm", feedback.kind === "error" ? "text-orange" : "text-green")}>
            {feedback.text}
          </p>
        )}
      </div>
      {open === "new" && (
        <Panel as="section" aria-label="Nouveau jeu">
          <GameForm initial={blank} creating roles={roles} channels={channels} busy={busy} onSubmit={d => void create(d)} onCancel={() => setOpen(null)} />
        </Panel>
      )}
      {games.length === 0 ? (
        <p className="m-0 text-muted">Aucun jeu pour l’instant.</p>
      ) : (
        <ol className="m-0 grid list-none gap-3 p-0">
          {games.map((g, i) => (
            <Panel as="li" key={g.key} className={cn("grid gap-4 p-5", !g.active && "opacity-70")}>
              <div className="flex flex-wrap items-center gap-3">
                <span className="size-5 flex-none rounded-md border border-white/20" style={{ background: g.color }} aria-hidden="true" />
                <div className="min-w-0 flex-1">
                  <p className="m-0 font-semibold">
                    {g.name} <span className="font-mono text-xs font-normal text-muted">{g.key}</span>
                  </p>
                  <p className="m-0 truncate text-sm text-muted">{g.tagline ?? "Sans accroche (texte générique)"}</p>
                </div>
                <Chip color={g.active ? "var(--color-green)" : "var(--color-muted)"}>{g.active ? "Actif" : "Désactivé"}</Chip>
                <div className="flex gap-1">
                  <Button size="sm" variant="ghost" aria-label={`Monter ${g.name}`} disabled={busy || i === 0} onClick={() => void move(i, -1)}>
                    <ArrowUp className="size-4" aria-hidden="true" />
                  </Button>
                  <Button size="sm" variant="ghost" aria-label={`Descendre ${g.name}`} disabled={busy || i === games.length - 1} onClick={() => void move(i, 1)}>
                    <ArrowDown className="size-4" aria-hidden="true" />
                  </Button>
                </div>
                <Button size="sm" variant="ghost" aria-expanded={open === g.key} onClick={() => setOpen(open === g.key ? null : g.key)}>
                  Modifier
                </Button>
                <Button size="sm" variant="ghost" disabled={busy} onClick={() => void setActive(g, !g.active)}>
                  {g.active ? "Désactiver" : "Réactiver"}
                </Button>
              </div>
              {open === g.key && (
                <GameForm initial={g} creating={false} roles={roles} channels={channels} busy={busy} onSubmit={d => void update(g.key, d)} onCancel={() => setOpen(null)} />
              )}
            </Panel>
          ))}
        </ol>
      )}
    </div>
  )
}
