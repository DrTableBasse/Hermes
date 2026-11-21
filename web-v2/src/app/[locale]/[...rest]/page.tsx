import { notFound } from "next/navigation"

/** URL inconnue : on laisse `not-found.tsx` s'afficher dans le layout du site (navbar, pied de page). */
export default function CatchAll() {
  notFound()
}
