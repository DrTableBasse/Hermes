import { adminEntryHref } from "@/lib/admin-sections"
import { PERMISSIONS } from "@/lib/permissions"

export type NavLink = { href: string; label: string }

/** Menu principal (spec §5.3). */
export const MAIN_LINKS: NavLink[] = [
  { href: "/", label: "Accueil" },
  { href: "/#jeux", label: "Jeux" },
  { href: "/progression", label: "Progression" },
  { href: "/hermes", label: "Hermes" },
  { href: "/galerie", label: "Galerie" },
]

/**
 * Espace connecté. `requires` restreint l'entrée : `articles.write`, ou `admin` (au moins un droit
 * qui ouvre une section de l'administration ; le lien mène alors à la première section ouverte).
 */
export const ACCOUNT_LINKS: Array<NavLink & { requires?: "articles.write" | "admin" }> = [
  { href: "/profil", label: "Profil" },
  { href: "/quetes", label: "Quêtes" },
  { href: "/tickets", label: "Tickets" },
  { href: "/editeur/nouveau", label: "Écrire un article", requires: "articles.write" },
  { href: "/admin", label: "Admin", requires: "admin" },
]

const ALL_PERMISSIONS = Object.keys(PERMISSIONS)

/** Droits de la session BetterAuth ; une session antérieure à `sitePermissions` retombe sur `isAdmin`/`isRedacteur`. */
export function sessionPermissions(user: {
  sitePermissions?: readonly string[] | null
  isAdmin?: boolean
  isRedacteur?: boolean
}): readonly string[] {
  if (Array.isArray(user.sitePermissions)) return user.sitePermissions
  if (user.isAdmin) return ALL_PERMISSIONS
  return user.isRedacteur ? ["articles.write"] : []
}

/** Entrées de l'espace connecté pour ces droits, « Admin » pointant sur la première section ouverte. */
export function accountLinks(permissions: readonly string[]): NavLink[] {
  const adminHref = adminEntryHref(permissions)
  return ACCOUNT_LINKS.flatMap(({ requires, ...link }) => {
    if (requires === "admin") return adminHref ? [{ ...link, href: adminHref }] : []
    if (requires && !permissions.includes(requires)) return []
    return [link]
  })
}

/** Lien actif : chemin exact, préfixe de locale retiré ; les ancres ne sont jamais « courantes ». */
export function isCurrent(href: string, pathname: string): boolean {
  if (href.includes("#")) return false
  const path = pathname.replace(/^\/fr(?=\/|$)/, "") || "/"
  return href === "/" ? path === "/" : path === href || path.startsWith(`${href}/`)
}
