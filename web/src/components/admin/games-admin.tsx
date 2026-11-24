"use client"

import { ArrowDown, ArrowUp } from "lucide-react"
import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Chip } from "@/components/ui/chip"
import { Panel } from "@/components/ui/panel"
import { api } from "@/lib/api/client"
import type { AdminGame, DiscordChannel, DiscordRole, GameInput, GameProvisionResult } from "@/lib/api/types"
import { cn } from "@/lib/cn"
import { ConfirmButton } from "./confirm-button"
import { botActionErrorText, type Feedback } from "./form"
import { GameForm, type GameDraft } from "./game-form"

type Props = { games: AdminGame[]; roles: DiscordRole[] | null; channels: DiscordChannel[] | null }

/** Retour d'une ligne : `pending` = action Discord en cours (jusqu'à 70 s), la page reste utilisable. */
type Note = { kind: "ok" | "error" | "pending"; text: string }

const byPosition = (a: AdminGame, b: AdminGame) => a.position - b.position || a.key.localeCompare(b.key)

const EDITABLE = ["name", "emoji", "color", "command_name", "tagline", "image", "position", "discord_role_id", "forum_channel_id"] as const

const toDraft = (g: AdminGame): GameDraft => ({
  key: g.key,
  name: g.name,
  emoji: g.emoji ?? "",
  color: g.color,
  command_name: g.command_name ?? "",
  tagline: g.tagline,
  image: g.image,
  position: g.position,
  discord_role_id: g.discord_role_id,
  forum_channel_id: g.forum_channel_id,
})

/** Champs modifiés seulement : un nom de commande inchangé n'est pas revérifié auprès du bot. */
function changes(g: AdminGame, d: GameDraft): Partial<GameInput> {
  const before = toDraft(g)
  return Object.fromEntries(EDITABLE.filter(k => d[k] !== before[k]).map(k => [k, d[k]]))
}

type State = "disabled" | "unprovisioned" | "repair" | "ok" | "unknown"

export function gameState(g: AdminGame): State {
  if (g.archived || !g.active) return "disabled"
  if (!g.provisioned) return "unprovisioned"
  if (!g.status) return "unknown"
  const { role, forum, command } = g.status
  return role === "missing" || forum === "missing" || command === "missing" ? "repair" : "ok"
}

/** Récapitulatif du provisionnement : rôle et forum créés ou réutilisés, commande sous une minute. */
export function provisionSummary(name: string, r: GameProvisionResult): string {
  const role = r.created.includes("role") ? "rôle créé" : "rôle existant réutilisé"
  const forum = r.created.includes("forum") ? "forum créé" : "forum existant réutilisé"
  const command = r.command
    ? `commande /${r.command} disponible dans la minute`
    : "aucune commande (choisis-en une dans « Modifier »)"
  return `« ${name} » prêt : ${role}, ${forum}, ${command}.`
}

const PART_LABEL = { role: "rôle", forum: "forum", command: "commande" } as const

function StatusChips({ g }: { g: AdminGame }) {
  if (!g.status) return <Chip color="var(--color-muted)">État Discord inconnu</Chip>
  return (
    <>
      {(["role", "forum", "command"] as const).map(part => {
        const value = g.status![part]
        if (value === "none") return null
        const ok = value === "ok"
        return (
          <Chip key={part} color={ok ? "var(--color-green)" : "var(--color-orange)"}>
            {PART_LABEL[part]} {ok ? <><span aria-hidden="true">✓</span><span className="sr-only">en place</span></> : "à recréer"}
          </Chip>
        )
      })}
    </>
  )
}

/**
 * Jeux de la communauté. Ajouter un jeu enchaîne création et provisionnement (rôle, forum, commande) ;
 * « Désactiver » archive côté Discord et retire du site, « Réactiver » rétablit. Les actions Discord
 * d'une ligne n'immobilisent que cette ligne.
 */
export function GamesAdmin({ games: initial, roles, channels }: Props) {
  const [games, setGames] = useState([...initial].sort(byPosition))
  const [open, setOpen] = useState<string | null>(null)
  const [notes, setNotes] = useState<Record<string, Note>>({})
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)
  const [moving, setMoving] = useState(false)
  const [orderFeedback, setOrderFeedback] = useState<Feedback>(null)

  const note = (key: string, n: Note | null) =>
    setNotes(all => {
      const next = { ...all }
      if (n) next[key] = n
      else delete next[key]
      return next
    })
  const patch = (key: string, p: Partial<AdminGame>) =>
    setGames(list => list.map(g => (g.key === key ? { ...g, ...p } : g)).sort(byPosition))

  /** Action Discord d'une ligne : « en cours… », puis le retour (succès ou erreur traduite). */
  async function act(g: AdminGame, pendingText: string, action: () => Promise<string>) {
    note(g.key, { kind: "pending", text: pendingText })
    try {
      note(g.key, { kind: "ok", text: await action() })
    } catch (e) {
      note(g.key, { kind: "error", text: botActionErrorText(e) })
    }
  }

  const provision = (g: AdminGame) =>
    act(g, `Création du rôle, du forum et de la commande de « ${g.name} » en cours… (jusqu’à une minute)`, async () => {
      const r = await api.admin.provisionGame(g.key)
      patch(g.key, {
        provisioned: true,
        discord_role_id: r.role_id,
        forum_channel_id: r.forum_id,
        status: r.status ?? { role: "ok", forum: "ok", command: r.command ? "ok" : "none" },
      })
      return provisionSummary(g.name, r)
    })

  async function create(d: GameDraft) {
    setCreating(true)
    setCreateError(null)
    const body = {
      key: d.key, name: d.name, emoji: d.emoji, color: d.color, command_name: d.command_name,
      tagline: d.tagline, image: d.image, position: d.position,
    }
    try {
      await api.admin.createGame(body)
    } catch (e) {
      setCreateError(botActionErrorText(e))
      return
    } finally {
      setCreating(false)
    }
    const game: AdminGame = {
      ...body, discord_role_id: null, forum_channel_id: null, active: true, lfg_cooldown: 3600,
      provisioned: false, archived: false, status: null,
    }
    setGames(list => [...list, game].sort(byPosition))
    setOpen(null)
    await provision(game)
  }

  const update = (g: AdminGame, d: GameDraft) =>
    act(g, "Enregistrement…", async () => {
      const diff = changes(g, d)
      if (Object.keys(diff).length === 0) {
        setOpen(null)
        return "Aucun changement."
      }
      const res = await api.admin.updateGame(g.key, diff)
      patch(g.key, diff as Partial<AdminGame>)
      setOpen(null)
      return res.bot_reloaded
        ? `« ${d.name} » enregistré.`
        : `« ${d.name} » enregistré. Hermes ne répond pas : il appliquera le changement à son prochain démarrage.`
    })

  const deactivate = (g: AdminGame) =>
    act(g, `Désactivation de « ${g.name} » en cours…`, async () => {
      const r = await api.admin.deactivateGame(g.key)
      patch(g.key, { archived: true, active: false, status: r.status ?? g.status })
      return `« ${g.name} » désactivé : commande retirée, forum archivé, rôle gardé. Il n’apparaît plus sur le site.`
    })

  const reactivate = (g: AdminGame) =>
    act(g, `Réactivation de « ${g.name} » en cours…`, async () => {
      const r = await api.admin.reactivateGame(g.key)
      patch(g.key, { archived: false, active: true, status: r.status ?? g.status })
      return `« ${g.name} » réactivé : commande et forum rétablis, de retour sur le site.`
    })

  /** Échange avec le voisin puis renumérote 1…n ; seules les positions modifiées sont envoyées. */
  async function move(index: number, delta: -1 | 1) {
    setMoving(true)
    setOrderFeedback(null)
    try {
      const next = [...games]
      ;[next[index], next[index + delta]] = [next[index + delta], next[index]]
      const renumbered = next.map((g, i) => ({ ...g, position: i + 1 }))
      for (const g of renumbered) {
        if (games.find(x => x.key === g.key)?.position !== g.position) await api.admin.updateGame(g.key, { position: g.position })
      }
      setGames(renumbered)
      setOrderFeedback({ kind: "ok", text: "Ordre enregistré." })
    } catch (e) {
      setOrderFeedback({ kind: "error", text: botActionErrorText(e) })
    } finally {
      setMoving(false)
    }
  }

  const nextPosition = games.reduce((m, g) => Math.max(m, g.position), 0) + 1
  const blank: GameDraft = {
    key: "", name: "", emoji: "", color: "#9B6BFF", command_name: "", tagline: null, image: null,
    position: nextPosition, discord_role_id: null, forum_channel_id: null,
  }

  return (
    <div className="grid gap-6">
      <div className="flex flex-wrap items-center gap-3">
        <Button size="sm" aria-expanded={open === "new"} onClick={() => setOpen(open === "new" ? null : "new")}>
          Ajouter un jeu
        </Button>
        {orderFeedback && (
          <p role={orderFeedback.kind === "error" ? "alert" : "status"} className={cn("m-0 text-sm", orderFeedback.kind === "error" ? "text-orange" : "text-green")}>
            {orderFeedback.text}
          </p>
        )}
      </div>
      {open === "new" && (
        <Panel as="section" aria-label="Nouveau jeu" className="grid gap-3">
          <GameForm initial={blank} creating roles={roles} channels={channels} busy={creating} onSubmit={d => void create(d)} onCancel={() => setOpen(null)} />
          {createError && (
            <p role="alert" className="m-0 text-sm text-orange">
              {createError}
            </p>
          )}
        </Panel>
      )}
      {games.length === 0 ? (
        <p className="m-0 text-muted">Aucun jeu pour l’instant.</p>
      ) : (
        <ol className="m-0 grid list-none gap-3 p-0">
          {games.map((g, i) => {
            const state = gameState(g)
            const n = notes[g.key]
            const pending = n?.kind === "pending"
            return (
              <Panel as="li" key={g.key} aria-busy={pending || undefined} className={cn("grid gap-4 p-5", state === "disabled" && "opacity-80")}>
                <div className="flex flex-wrap items-center gap-3">
                  <span className="size-5 flex-none rounded-md border border-white/20" style={{ background: g.color }} aria-hidden="true" />
                  <div className="min-w-0 flex-1">
                    <p className="m-0 font-semibold">
                      {g.emoji && <span aria-hidden="true">{g.emoji} </span>}
                      {g.name}
                      {state === "disabled" && <span className="font-normal text-muted"> (désactivé)</span>}{" "}
                      <span className="font-mono text-xs font-normal text-muted">{g.command_name ? `/${g.command_name}` : "—"}</span>
                    </p>
                    <p className="m-0 truncate text-sm text-muted">{g.tagline ?? "Sans accroche (texte générique)"}</p>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {state === "disabled" ? (
                      <Chip color="var(--color-muted)">Désactivé</Chip>
                    ) : state === "unprovisioned" ? (
                      <Chip color="var(--color-gold)">Non provisionné</Chip>
                    ) : (
                      <StatusChips g={g} />
                    )}
                  </div>
                  <div className="flex gap-1">
                    <Button size="sm" variant="ghost" aria-label={`Monter ${g.name}`} disabled={moving || i === 0} onClick={() => void move(i, -1)}>
                      <ArrowUp className="size-4" aria-hidden="true" />
                    </Button>
                    <Button size="sm" variant="ghost" aria-label={`Descendre ${g.name}`} disabled={moving || i === games.length - 1} onClick={() => void move(i, 1)}>
                      <ArrowDown className="size-4" aria-hidden="true" />
                    </Button>
                  </div>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  {state === "unprovisioned" && (
                    <Button size="sm" disabled={pending} onClick={() => void provision(g)}>
                      Créer le rôle, le forum et la commande
                    </Button>
                  )}
                  {state === "repair" && (
                    <Button size="sm" disabled={pending} onClick={() => void provision(g)}>
                      Recréer ce qui manque
                    </Button>
                  )}
                  <Button size="sm" variant="ghost" aria-expanded={open === g.key} disabled={pending} onClick={() => setOpen(open === g.key ? null : g.key)}>
                    Modifier
                  </Button>
                  {state === "disabled" ? (
                    <Button size="sm" variant="ghost" disabled={pending} onClick={() => void reactivate(g)}>
                      Réactiver
                    </Button>
                  ) : (
                    <ConfirmButton
                      question={`Désactiver « ${g.name} » ? Commande retirée, forum archivé, rôle gardé.`}
                      confirmLabel="Désactiver"
                      disabled={pending}
                      onConfirm={() => deactivate(g)}
                    >
                      Désactiver
                    </ConfirmButton>
                  )}
                </div>
                {n && (
                  <p
                    role={n.kind === "error" ? "alert" : "status"}
                    className={cn("m-0 text-sm", n.kind === "error" ? "text-orange" : n.kind === "ok" ? "text-green" : "text-muted")}
                  >
                    {n.text}
                  </p>
                )}
                {open === g.key && (
                  <GameForm initial={toDraft(g)} creating={false} roles={roles} channels={channels} busy={pending} onSubmit={d => void update(g, d)} onCancel={() => setOpen(null)} />
                )}
              </Panel>
            )
          })}
        </ol>
      )}
    </div>
  )
}
