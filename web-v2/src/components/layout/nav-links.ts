export type NavLink = { href: string; label: string }

/** Menu principal (spec §5.3). */
export const MAIN_LINKS: NavLink[] = [
  { href: "/", label: "Accueil" },
  { href: "/#jeux", label: "Jeux" },
  { href: "/progression", label: "Progression" },
  { href: "/hermes", label: "Hermes" },
  { href: "/galerie", label: "Galerie" },
]

/** Espace connecté ; `role` restreint l'entrée aux membres qui portent ce rôle. */
export const ACCOUNT_LINKS: Array<NavLink & { role?: "isAdmin" | "isRedacteur" }> = [
  { href: "/profil", label: "Profil" },
  { href: "/quetes", label: "Quêtes" },
  { href: "/tickets", label: "Tickets" },
  { href: "/editeur/nouveau", label: "Écrire un article", role: "isRedacteur" },
  { href: "/admin", label: "Admin", role: "isAdmin" },
]

/** Lien actif : chemin exact, préfixe de locale retiré ; les ancres ne sont jamais « courantes ». */
export function isCurrent(href: string, pathname: string): boolean {
  if (href.includes("#")) return false
  const path = pathname.replace(/^\/fr(?=\/|$)/, "") || "/"
  return href === "/" ? path === "/" : path === href || path.startsWith(`${href}/`)
}
