"use client"

import { useId, useState, type CSSProperties, type FormEvent } from "react"
import { Button } from "@/components/ui/button"
import { api, ApiError } from "@/lib/api/client"
import type { Game } from "@/lib/api/types"
import { cn } from "@/lib/cn"

/** Limites de `PUT /staff/me` (`web-api/routes/staff.py` : MOTTO_MAX, GAMES_MAX). */
export const MOTTO_MAX = 140
export const GAMES_MAX = 5

type StaffProfileFormProps = {
  /** Phrase enregistrée (`null` : aucune). */
  motto: string | null
  /** Clés des jeux enregistrés. */
  selected: string[]
  /** Jeux actifs (`GET /games`) ; `null` : liste indisponible, les jeux enregistrés sont conservés tels quels. */
  games: Game[] | null
}

type Feedback = { kind: "ok" | "error"; text: string } | null

/** Longueur comptée comme Python (`len`) : en points de code, un emoji vaut un caractère. */
const length = (text: string) => [...text].length

/** Retours à la ligne et séparateurs de ligne collés : remplacés par une espace (l'API les refuse). */
const LINE_BREAKS = new RegExp(`[\\r\\n${String.fromCharCode(0x2028, 0x2029)}]+`, "g")
const oneLine = (text: string) => text.replace(LINE_BREAKS, " ")

// Autres caractères de contrôle (tabulation, caractères invisibles collés) : refusés par l'API.
const CONTROL = /[\u0000-\u001F\u007F-\u009F]/

function errorText(error: unknown): string {
  if (!(error instanceof ApiError)) return "Envoi impossible : le site ne répond pas. Vérifie ta connexion et réessaie."
  switch (error.status) {
    case 401:
      return "Ta session a expiré : reconnecte-toi avec Discord, puis réessaie."
    case 403:
      return "Tu ne fais pas partie de l’état-major : seuls ses membres ont une carte à modifier."
    case 422:
      // Message de validation de web-api, déjà rédigé pour un humain (« 5 jeux maximum »…).
      return `Profil refusé : ${error.message.replace(/\.$/, "")}.`
    case 429:
      return "Trop d’enregistrements d’affilée : attends une minute avant de réessayer."
    case 503:
      return "L’état-major est indisponible pour l’instant (Hermes ou la base ne répond pas). Réessaie dans un moment."
    default:
      return `Enregistrement impossible (erreur ${error.status}). Réessaie dans un moment.`
  }
}

/** Édition de sa propre carte de l'état-major : phrase perso et jeux (`PUT /staff/me`). */
export function StaffProfileForm({ motto: initialMotto, selected: initialGames, games }: StaffProfileFormProps) {
  const ids = useId()
  const [motto, setMotto] = useState(initialMotto ?? "")
  const [selected, setSelected] = useState(initialGames)
  const [sending, setSending] = useState(false)
  const [feedback, setFeedback] = useState<Feedback>(null)

  const trimmed = motto.trim()
  const mottoLength = length(trimmed)
  const mottoError =
    mottoLength > MOTTO_MAX
      ? `${MOTTO_MAX} caractères maximum : retires-en ${mottoLength - MOTTO_MAX}.`
      : CONTROL.test(trimmed)
        ? "La phrase contient un caractère invisible (tabulation…) : retire-le."
        : null
  const gamesError =
    selected.length > GAMES_MAX ? `${GAMES_MAX} jeux maximum : décoche-en ${selected.length - GAMES_MAX}.` : null
  const blocked = mottoError !== null || gamesError !== null

  function toggle(key: string) {
    setFeedback(null)
    setSelected(current => (current.includes(key) ? current.filter(k => k !== key) : [...current, key]))
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (blocked || sending) return
    setSending(true)
    setFeedback(null)
    try {
      await api.staff.updateMyProfile({ motto: trimmed || null, games: selected })
      setFeedback({
        kind: "ok",
        text: "Profil enregistré. La page de l’état-major l’affichera d’ici quelques minutes.",
      })
    } catch (error) {
      setFeedback({ kind: "error", text: errorText(error) })
    } finally {
      setSending(false)
    }
  }

  const mottoId = `${ids}-motto`
  const mottoHelp = `${ids}-motto-help`
  const gamesHelp = `${ids}-games-help`

  return (
    <form onSubmit={onSubmit} noValidate className="grid gap-7">
      <div className="grid gap-2">
        <label htmlFor={mottoId} className="font-display text-lg font-bold">
          Ta phrase
        </label>
        <textarea
          id={mottoId}
          rows={2}
          value={motto}
          onChange={e => {
            setFeedback(null)
            setMotto(oneLine(e.target.value))
          }}
          // Une seule ligne : Entrée enregistre au lieu d'ajouter un retour à la ligne.
          onKeyDown={e => {
            if (e.key === "Enter") {
              e.preventDefault()
              e.currentTarget.form?.requestSubmit()
            }
          }}
          aria-invalid={mottoError !== null}
          aria-describedby={mottoHelp}
          placeholder="« Je modère de 22 h à 3 h. Oui, je dors parfois. »"
          className={cn(
            "resize-none rounded-[14px] border bg-[rgb(12_14_26/0.6)] px-4 py-3 text-[15px] text-fg placeholder:text-muted/70",
            mottoError ? "border-orange" : "border-white/14 focus:border-violet/60",
          )}
        />
        <div id={mottoHelp} className="flex flex-wrap justify-between gap-2 text-sm">
          <span className={mottoError ? "text-orange" : "text-muted"}>
            {mottoError ?? "Une ligne, affichée entre guillemets sur ta carte. Vide : pas de phrase."}
          </span>
          <span className={cn("tabular-nums", mottoLength > MOTTO_MAX ? "text-orange" : "text-muted")}>
            {mottoLength} / {MOTTO_MAX}
          </span>
        </div>
      </div>

      <fieldset className="m-0 grid gap-3 border-0 p-0" aria-describedby={gamesHelp}>
        <legend className="mb-2 p-0 font-display text-lg font-bold">Tes jeux</legend>
        {games === null ? (
          <p id={gamesHelp} className="m-0 text-sm text-muted">
            Liste des jeux indisponible pour l’instant : tes jeux actuels sont conservés.
          </p>
        ) : games.length === 0 ? (
          <p id={gamesHelp} className="m-0 text-sm text-muted">
            Aucun jeu n’est encore ouvert sur le site.
          </p>
        ) : (
          <>
            <div className="flex flex-wrap gap-2.5">
              {games.map(g => {
                const checked = selected.includes(g.key)
                return (
                  <label
                    key={g.key}
                    style={{ "--c": g.color } as CSSProperties}
                    className={cn(
                      "inline-flex cursor-pointer items-center gap-2 rounded-full border px-3.5 py-2 text-sm font-semibold transition-colors",
                      "has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-cyan",
                      checked
                        ? "border-[color-mix(in_srgb,var(--c)_60%,transparent)] bg-[color-mix(in_srgb,var(--c)_18%,transparent)] text-[color-mix(in_oklab,var(--c)_60%,white)]"
                        : "border-white/14 bg-white/4 text-muted hover:text-fg",
                    )}
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggle(g.key)}
                      className="size-4 accent-(--c)"
                    />
                    {g.name}
                  </label>
                )
              })}
            </div>
            <div id={gamesHelp} className="flex flex-wrap justify-between gap-2 text-sm">
              <span className={gamesError ? "text-orange" : "text-muted"}>
                {gamesError ?? `Jusqu’à ${GAMES_MAX} jeux, affichés sous ta phrase.`}
              </span>
              <span className={cn("tabular-nums", gamesError ? "text-orange" : "text-muted")}>
                {selected.length} / {GAMES_MAX}
              </span>
            </div>
          </>
        )}
      </fieldset>

      <div className="flex flex-wrap items-center gap-4">
        <Button type="submit" disabled={sending} aria-disabled={blocked || undefined} className={cn(blocked && "opacity-50")}>
          {sending ? "Enregistrement…" : "Enregistrer"}
        </Button>
        {feedback?.kind === "ok" && (
          <p role="status" className="m-0 text-sm text-green">
            {feedback.text}
          </p>
        )}
        {feedback?.kind === "error" && (
          <p role="alert" className="m-0 text-sm text-orange">
            {feedback.text}
          </p>
        )}
      </div>
    </form>
  )
}
