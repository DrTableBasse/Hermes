import type { RoleRule, RoleRuleCondition } from "@/lib/api/types"

/**
 * Conditions des règles automatiques (liste fermée, même ordre que web-api) et leur libellé.
 * Module neutre : importable par les pages serveur comme par les composants client.
 */
export const RULE_CONDITIONS = [
  { key: "voice_hours", label: "Vocal total (heures)" },
  { key: "messages", label: "Messages total" },
  { key: "level", label: "Niveau XP" },
  { key: "grade", label: "Grade" },
  { key: "achievement", label: "Succès débloqué" },
  { key: "streak_days", label: "Série vocale (jours)" },
  { key: "bumps", label: "Bumps" },
  { key: "invites", label: "Invitations" },
] as const satisfies ReadonlyArray<{ key: RoleRuleCondition; label: string }>

type Names = { grades?: ReadonlyMap<string, string> }

/** « Vocal total ≥ 100 h », « Succès « Moulin à paroles » », « Grade « Saucisson » »… */
export function conditionText(rule: Pick<RoleRule, "condition_type" | "condition_value" | "achievement_name">, names: Names = {}): string {
  const v = rule.condition_value
  switch (rule.condition_type) {
    case "voice_hours":
      return `Vocal total ≥ ${v} h`
    case "messages":
      return `Messages total ≥ ${v}`
    case "level":
      return `Niveau XP ≥ ${v}`
    case "grade":
      return `Grade « ${names.grades?.get(v) ?? v} »`
    case "achievement":
      return `Succès « ${rule.achievement_name ?? `n° ${v}`} »`
    case "streak_days":
      return `Série vocale ≥ ${v} jours`
    case "bumps":
      return `Bumps ≥ ${v}`
    case "invites":
      return `Invitations ≥ ${v}`
  }
}
