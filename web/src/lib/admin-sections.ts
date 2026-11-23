/** Sections de l'administration. Module neutre (ni client ni serveur) : importable par la page serveur /admin comme par la navigation client. */
export const ADMIN_SECTIONS = [
  { href: "/admin", label: "Vue d’ensemble" },
  { href: "/admin/reglages", label: "Réglages" },
  { href: "/admin/moderation", label: "Modération" },
  { href: "/admin/commandes", label: "Commandes" },
  { href: "/admin/quetes", label: "Quêtes" },
  { href: "/admin/tickets", label: "Tickets" },
  { href: "/admin/galerie", label: "Galerie" },
  { href: "/admin/etat-major", label: "État-major" },
  { href: "/admin/jeux", label: "Jeux" },
  { href: "/admin/contenus", label: "Contenus" },
  { href: "/admin/analytique", label: "Analytique" },
] as const
