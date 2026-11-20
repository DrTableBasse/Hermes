/** Utilitaires d'URL partagés par `server.ts` et `client.ts` (aucune dépendance serveur). */

/** Segment de chemin variable : toujours encodé, pour qu'un identifiant ne puisse pas changer de route. */
export function seg(value: string | number): string {
  return encodeURIComponent(String(value))
}

/** Chaîne de requête (`?a=1&b=2`) ; les valeurs `undefined` ou vides sont omises. */
export function query(params: Record<string, string | number | undefined>): string {
  const qs = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") qs.set(key, String(value))
  }
  const text = qs.toString()
  return text ? `?${text}` : ""
}
