/**
 * Journal « en direct » d'Hermes : pure invention, assumée comme humour (spec §5.4). Aucun chiffre ni
 * pseudo réel, pour qu'aucune ligne ne passe pour une donnée du serveur.
 */
export type LogTag = "GRILL" | "BAR" | "XP" | "BUMP" | "TICKET" | "SUCCÈS" | "RECHERCHE" | "SYSTÈME" | "HUMOUR"

export type LogLine = { tag: LogTag; text: string }

/** Couleur de l'étiquette, lisible sur le fond du terminal. */
export const LOG_TAG_COLORS: Record<LogTag, string> = {
  GRILL: "#FF8A3D",
  BAR: "#F2C14E",
  XP: "#3FE0F0",
  BUMP: "#7FA0FF",
  TICKET: "#3BD16F",
  SUCCÈS: "#F2C14E",
  RECHERCHE: "#B394FF",
  SYSTÈME: "#9AA6C8",
  HUMOUR: "#B394FF",
}

export const HERMES_LOGS: readonly LogLine[] = [
  { tag: "GRILL", text: "Fait griller une chipolata sans la cramer. Succès." },
  { tag: "BAR", text: "Décapsule une bière sous 40 °C. Mousse maîtrisée." },
  { tag: "GRILL", text: "Retourne les merguez. Côté B impeccable." },
  { tag: "GRILL", text: "Calibre le barbecue à 220 °C. Les végétariens sont prévenus." },
  { tag: "GRILL", text: "Allume le barbecue sans flamber les sourcils de personne. Cette fois." },
  { tag: "GRILL", text: "Pique une saucisse pour vérifier la cuisson. Elle ne s’est pas plainte." },
  { tag: "BAR", text: "Range les canettes vides. Personne d’autre ne le fera." },
  { tag: "BAR", text: "Remplit le frigo de la cantine. Vide à nouveau. Hypothèse : des Généraux." },
  { tag: "BAR", text: "Sert un sirop à l’eau à un Général. Ne pose pas de questions." },
  { tag: "RECHERCHE", text: "Cherche la moutarde. Introuvable. Relance la recherche." },
  { tag: "RECHERCHE", text: "Cherche le sens de « gg ez ». Résultat : non concluant." },
  { tag: "RECHERCHE", text: "Cherche qui a laissé le micro ouvert. Indice : on entend un frigo." },
  { tag: "XP", text: "Distribue de l’XP. Personne ne dit merci. Continue quand même." },
  { tag: "XP", text: "Compte l’XP d’un membre qui dort en vocal. Le règlement est le règlement." },
  { tag: "XP", text: "Recalcule les niveaux de tout le monde. Trouve le même résultat. Rassuré." },
  { tag: "BUMP", text: "Rappelle le bump. Insiste poliment. Insiste un peu moins poliment." },
  { tag: "BUMP", text: "Attend la fin du délai de bump. Regarde l’horloge. L’horloge le regarde." },
  { tag: "TICKET", text: "Ouvre un ticket. Motif : saucisse coincée dans le vocal." },
  { tag: "TICKET", text: "Ferme un ticket. Le staff a résolu le problème. Hermes s’attribue le mérite." },
  { tag: "TICKET", text: "Garde un secret de ticket. Ne le dira même pas au barbecue." },
  { tag: "SUCCÈS", text: "Décerne un succès. Applaudit tout seul dans le salon serveur." },
  { tag: "SUCCÈS", text: "Garde les succès secrets secrets. C’est le principe." },
  { tag: "SYSTÈME", text: "Recompte les Généraux en ligne. Même nombre. Recompte quand même." },
  { tag: "SYSTÈME", text: "Fait une sieste de zéro seconde. Se sent reposé." },
  { tag: "SYSTÈME", text: "Met à jour son humeur. Version stable : pince-sans-rire." },
  { tag: "SYSTÈME", text: "Vérifie que le serveur tient debout. Il tient. Bon soldat." },
  { tag: "HUMOUR", text: "Tente de comprendre une blague du vocal. Échec. Réessaie demain." },
  { tag: "HUMOUR", text: "Raconte une blague au staff. Silence radio. Note l’incident." },
  { tag: "HUMOUR", text: "Apprend le second degré. Progression : 12 %. Ou pas." },
]

/** Générateur pseudo-aléatoire déterministe (mulberry32) : même graine, même suite. */
function mulberry32(seed: number): () => number {
  let a = seed >>> 0
  return () => {
    a = (a + 0x6d2b79f5) >>> 0
    let t = a
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

/** `n` lignes distinctes du journal (au plus toutes), dans un ordre fixé par `seed`. */
export function pickLogLines(seed: number, n: number): LogLine[] {
  const random = mulberry32(seed)
  const lines = [...HERMES_LOGS]
  // Fisher-Yates.
  for (let i = lines.length - 1; i > 0; i--) {
    const j = Math.floor(random() * (i + 1))
    ;[lines[i], lines[j]] = [lines[j], lines[i]]
  }
  return lines.slice(0, Math.max(0, Math.min(n, lines.length)))
}
