type Redirect = { source: string; destination: string; permanent: true }

/** Pages renommées de l'ancien site (web v1) → page du nouveau. `/editor/new` précède `/editor/:id`. */
const RENAMED: Array<[string, string]> = [
  ["/leaderboard", "/classement"],
  ["/profile", "/profil"],
  ["/quests", "/quetes"],
  ["/compare", "/comparer"],
  ["/top-weekly", "/top-semaine"],
  ["/editor/new", "/editeur/nouveau"],
  ["/editor/:id", "/editeur/:id"],
]

/** Préfixes de langue de l'ancien site (`localePrefix: 'always'`, fr et en) ; le nouveau est sans préfixe. */
const LOCALES = ["/fr", "/en"]

/**
 * Redirections permanentes des anciennes URL (`redirects()` de next.config.ts). Next applique la
 * première règle qui correspond : chaque ancienne URL arrive sur sa page en une seule redirection,
 * préfixe et renommage compris (`/en/leaderboard` → `/classement`). La requête (`?…`) est conservée.
 */
export function legacyRedirects(): Redirect[] {
  const rules: Redirect[] = []
  for (const prefix of ["", ...LOCALES]) {
    for (const [from, to] of RENAMED) rules.push({ source: `${prefix}${from}`, destination: to, permanent: true })
  }
  for (const prefix of LOCALES) {
    rules.push({ source: prefix, destination: "/", permanent: true })
    rules.push({ source: `${prefix}/:path*`, destination: "/:path*", permanent: true })
  }
  return rules
}
