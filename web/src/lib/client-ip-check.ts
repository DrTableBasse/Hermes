import { CLIENT_IP_MARKER } from "@/lib/api/forward"

/**
 * Constat m6 : sans le preload `runtime/client-ip.cjs`, aucune IP n'est relayée à web-api et tous
 * les visiteurs partagent le compteur du limiteur (l'IP du conteneur `web`). Ce contrôle, appelé
 * au démarrage du serveur (`instrumentation.ts`), rend cette absence visible dans les logs.
 * Renvoie `true` si un avertissement a été émis.
 */
export function warnIfClientIpPreloadMissing(
  env: Record<string, string | undefined> = process.env,
  warn: (message: string) => void = console.warn,
): boolean {
  if (env["NODE_ENV"] !== "production" || env[CLIENT_IP_MARKER]) return false
  warn(
    `[client-ip] ATTENTION : preload absent (${CLIENT_IP_MARKER} non défini). Aucune IP visiteur ` +
      "n'est relayée à web-api : tous les visiteurs partagent un seul compteur du limiteur. " +
      "Lancer le serveur avec « node --require ./runtime/preload.cjs server.js » (voir Dockerfile).",
  )
  return true
}
