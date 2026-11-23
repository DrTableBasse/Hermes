/** Exécuté une fois au démarrage du serveur Next (runtime Node et Edge). */
export async function register() {
  if (process.env.NEXT_RUNTIME !== "nodejs") return
  const { warnIfClientIpPreloadMissing } = await import("@/lib/client-ip-check")
  warnIfClientIpPreloadMissing()
}
