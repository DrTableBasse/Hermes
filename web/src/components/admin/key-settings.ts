import type { SettingItem } from "@/lib/api/types"

/** Réglages que le propriétaire doit avoir faits : signalés sur la vue d'ensemble et dans Réglages. */
export const KEY_SETTINGS = [
  { key: "invite_url", why: "Lien d’invitation Discord des boutons « Rejoindre » du site." },
  { key: "ticket_panel_channel", why: "Salon où Hermes pose le panneau d’ouverture des tickets." },
  { key: "mod_role", why: "Rôle de modération affiché sur l’état-major et reconnu par Hermes." },
] as const

export const isIdKind = (kind: string) => kind === "channel" || kind === "category" || kind === "role"

export const isKeySetting =(key: string) => KEY_SETTINGS.some(k => k.key === key)

/** État lisible d'un réglage : vide, introuvable sur Discord, non vérifiable (bot muet) ou réglé. */
export function settingState(item: SettingItem | undefined): { ok: boolean; label: string } {
  if (!item || item.value === "") return { ok: false, label: "À régler" }
  // Défaut du registre par nom (« Modération ») : aucun rôle choisi tant qu'aucun identifiant n'est enregistré.
  if (isIdKind(item.kind) && !/^\d+$/.test(item.value)) return { ok: false, label: "À choisir" }
  if (item.resolved?.exists === false) return { ok: false, label: "Introuvable sur Discord" }
  if (item.resolved && item.resolved.exists === null) return { ok: false, label: "Non vérifié (bot muet)" }
  return { ok: true, label: item.resolved?.name ? `Réglé : ${item.resolved.name}` : "Réglé" }
}
