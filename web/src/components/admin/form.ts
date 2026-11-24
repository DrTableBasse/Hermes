import { ApiError } from "@/lib/api/client"

/** Classes communes des champs de l'administration. */
export const FIELD =
  "w-full rounded-xl border border-white/14 bg-[rgb(12_14_26/0.6)] px-3.5 py-2.5 text-[15px] text-fg placeholder:text-muted/70 focus:border-violet/60 aria-[invalid=true]:border-orange"
export const LABEL = "text-sm font-semibold text-fg"

export type Feedback = { kind: "ok" | "error"; text: string } | null

/** Messages par défaut d'une erreur sans détail : `statusText` du navigateur ou repli du client. */
const NO_DETAIL = new Set(["", "Forbidden", "Erreur API"])

/** Message lisible pour une erreur de web-api (403, 422 et 409 : le détail rédigé par l'API). */
export function adminErrorText(error: unknown): string {
  if (!(error instanceof ApiError)) return "Le site ne répond pas : vérifie ta connexion et réessaie."
  switch (error.status) {
    case 401:
      return "Ta session a expiré : reconnecte-toi avec Discord, puis réessaie."
    case 403:
      // « Droit requis : … » nomme le droit manquant, plus utile que le message générique.
      return NO_DETAIL.has(error.message) ? "Action réservée à l’administration." : error.message
    case 404:
      return `Introuvable : ${error.message}.`
    case 409:
    case 422:
    case 400:
      return `Refusé : ${error.message.replace(/\.$/, "")}.`
    case 429:
      return "Trop de requêtes d’affilée : attends une minute avant de réessayer."
    case 502:
    case 503:
      return "Hermes (le bot) ne répond pas pour l’instant. Réessaie dans un moment."
    case 504:
      return "Le site ne répond pas pour l’instant. Réessaie dans un moment."
    default:
      return `Échec (erreur ${error.status}). Réessaie dans un moment.`
  }
}

/** Libellés HTTP bruts (aucun détail rédigé par l'API). */
const STATUS_TEXT = new Set(["Bad Gateway", "Service Unavailable", "Gateway Timeout"])

/**
 * Comme `adminErrorText`, mais garde le détail des 502/503/504 rédigé par l'API pour les actions
 * Discord des jeux (« Erreur Discord : … », « Le bot n'a pas répondu à temps : … »).
 */
export function botActionErrorText(error: unknown): string {
  if (
    error instanceof ApiError &&
    (error.status === 502 || error.status === 503 || error.status === 504) &&
    !NO_DETAIL.has(error.message) &&
    !STATUS_TEXT.has(error.message)
  ) {
    return error.message
  }
  return adminErrorText(error)
}

/**
 * Erreur d'une action sur les salons : comme `botActionErrorText` (« Erreur Discord : … » gardé),
 * mais un délai dépassé (504, web-api ou proxy) dit que l'action se termine peut-être encore.
 */
export function channelActionErrorText(error: unknown): string {
  if (error instanceof ApiError && error.status === 504) {
    return "L’action se termine peut-être encore : rechargez la page dans un instant pour voir l’état des salons."
  }
  return botActionErrorText(error)
}
