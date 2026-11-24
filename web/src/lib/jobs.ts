import type { RoleJob } from "@/lib/api/types"

/** Délai entre deux relevés de l'état d'un travail du bot (`GET /admin/jobs/{id}`). */
export const JOB_POLL_MS = 1000

/** « 1 erreur », « 2 erreurs » (singulier pour 0 et 1, comme en français). */
export const plural = (n: number, word: string) => `${n} ${word}${n > 1 ? "s" : ""}`

/** Bilan d'un travail terminé : application d'une règle (ajoutés, retirés…) ou lot de membres. */
function tally(job: RoleJob): string {
  if (job.added !== undefined) {
    return [
      plural(job.added, "ajouté"),
      plural(job.removed ?? 0, "retiré"),
      `${job.skipped ?? 0} déjà pourvu${(job.skipped ?? 0) > 1 ? "s" : ""}`,
      plural(job.errors, "erreur"),
    ].join(", ")
  }
  return `${plural(job.done, "membre")} traité${job.done > 1 ? "s" : ""} sur ${job.total}, ${plural(job.errors, "erreur")}`
}

const processed = (job: RoleJob) => `${plural(job.done, "membre")} traité${job.done > 1 ? "s" : ""} sur ${job.total}`

/**
 * Texte de l'état d'un travail. `lost` : le bot ne le connaît plus (404 : redémarré ou suivi expiré),
 * `job` est alors le dernier état relevé, s'il y en a un.
 */
export function jobText(job: RoleJob | null, lost = false): string {
  const noResume = "rien n’est repris automatiquement."
  if (lost) {
    return `Interrompu : Hermes a redémarré ou le suivi a expiré${job ? ` (${processed(job)} au dernier relevé)` : ""} ; ${noResume}`
  }
  if (!job) return "En cours…"
  switch (job.state) {
    case "running":
      return job.total > 0 ? `En cours : ${job.done} sur ${job.total}…` : "En cours…"
    case "done":
      return job.missing_role ? "Terminé : rôle introuvable, rien n’a été attribué." : `Terminé : ${tally(job)}.`
    case "interrupted":
      return `Interrompu : ${processed(job)} avant l’arrêt d’Hermes ; ${noResume}`
    case "failed":
      return `Échec : ${processed(job)}, ${plural(job.errors, "erreur")}. Consulte le journal d’Hermes.`
  }
}

/** L'état appelle une alerte (interrompu, échec) plutôt qu'une annonce discrète. */
export const jobIsAlarming = (job: RoleJob | null, lost: boolean) =>
  lost || job?.state === "interrupted" || job?.state === "failed" || (job?.state === "done" && job.missing_role === true)
