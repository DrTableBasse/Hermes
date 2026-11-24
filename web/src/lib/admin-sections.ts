import type { SitePermission } from "@/lib/permissions"

/**
 * Sections de l'administration et droit exigé par chacune (celui des routes web-api qu'elle lit).
 * Module neutre (ni client ni serveur) : importable par les pages serveur comme par la navigation client.
 */
export const ADMIN_SECTIONS = [
  { href: "/admin", label: "Vue d’ensemble", permission: "admin.view" },
  { href: "/admin/reglages", label: "Réglages", permission: "settings.manage" },
  { href: "/admin/moderation", label: "Modération", permission: "moderation.view" },
  { href: "/admin/commandes", label: "Commandes", permission: "settings.manage" },
  { href: "/admin/quetes", label: "Quêtes", permission: "quests.manage" },
  { href: "/admin/tickets", label: "Tickets", permission: "tickets.manage" },
  { href: "/admin/galerie", label: "Galerie", permission: "gallery.manage" },
  { href: "/admin/etat-major", label: "État-major", permission: "content.edit" },
  { href: "/admin/jeux", label: "Jeux", permission: "games.manage" },
  { href: "/admin/contenus", label: "Contenus", permission: "content.edit" },
  { href: "/admin/analytique", label: "Analytique", permission: "analytics.view" },
  { href: "/admin/roles", label: "Rôles", permission: "roles.manage" },
  { href: "/admin/regles", label: "Règles", permission: "roles.manage" },
  { href: "/admin/acces", label: "Accès", permission: "permissions.manage" },
] as const satisfies ReadonlyArray<{ href: string; label: string; permission: SitePermission }>

export type AdminSection = (typeof ADMIN_SECTIONS)[number]

/** Sections que ces droits ouvrent, dans l'ordre de la navigation. */
export function allowedSections(permissions: readonly string[]): AdminSection[] {
  const has = new Set(permissions)
  return ADMIN_SECTIONS.filter(s => has.has(s.permission))
}

/** Au moins une section de l'administration est ouverte (entrée « Admin » du menu, cadre /admin). */
export function hasAdminAccess(permissions: readonly string[]): boolean {
  return allowedSections(permissions).length > 0
}

/** Première section ouverte : cible du lien « Admin » (la vue d'ensemble exige `admin.view`). */
export function adminEntryHref(permissions: readonly string[]): string | null {
  return allowedSections(permissions)[0]?.href ?? null
}
