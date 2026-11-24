import { Button } from "@/components/ui/button"
import { Panel } from "@/components/ui/panel"
import type { AdminGate } from "@/lib/admin-gate"
import { PERMISSIONS } from "@/lib/permissions"

function deniedText(gate: Exclude<AdminGate, { kind: "ok" }>): { code: string; title: string; body: string } {
  switch (gate.kind) {
    case "signin":
      return {
        code: "Connexion requise",
        title: "Connecte-toi pour continuer",
        body: "L’administration est réservée aux membres connectés avec Discord. Utilise « Connexion » dans le menu.",
      }
    case "unavailable":
      return {
        code: "Vérification impossible",
        title: "Impossible de vérifier tes droits",
        body: "Le site ne répond pas pour l’instant. Réessaie dans un moment.",
      }
    case "forbidden":
      return {
        code: "Erreur 403",
        title: "Zone réservée à l’administration",
        body: gate.anyOf
          ? `Cette page demande le droit ${gate.anyOf.map(p => `« ${PERMISSIONS[p]} »`).join(" ou ")}, que ton compte n’a pas. Si c’est une erreur, demande-le à un admin ; il prend effet sous 10 minutes.`
          : gate.permission
          ? `Cette page demande le droit « ${PERMISSIONS[gate.permission]} », que ton compte n’a pas. Si c’est une erreur, demande-le à un admin ; il prend effet sous 10 minutes.`
          : "Ton compte n’a aucun droit d’administration sur le site. Si c’est une erreur, demande-le à un admin puis reconnecte-toi.",
      }
  }
}

/** Accès refusé (403), connexion requise ou vérification impossible : page propre, sans rien des outils d'administration. */
export function AdminDenied({ gate }: { gate: Exclude<AdminGate, { kind: "ok" }> }) {
  const text = deniedText(gate)
  return (
    <div className="relative pt-6 pb-24">
      <div className="mx-auto max-w-[640px]">
        <Panel className="grid gap-4 text-center">
          <p className="m-0 font-mono text-sm text-muted">{text.code}</p>
          <h1 className="m-0 font-display text-3xl font-extrabold">{text.title}</h1>
          <p className="m-0 text-muted">{text.body}</p>
          <div>
            <Button href="/" variant="ghost">
              Retour à l’accueil
            </Button>
          </div>
        </Panel>
      </div>
    </div>
  )
}

/** Encadré d'information ou d'erreur de chargement d'une sous-page. */
export function AdminNote({ children, tone = "info" }: { children: React.ReactNode; tone?: "info" | "error" }) {
  return (
    <p
      role={tone === "error" ? "alert" : "status"}
      className={
        tone === "error"
          ? "m-0 rounded-2xl border border-orange/40 bg-orange/8 px-6 py-5 text-orange"
          : "m-0 rounded-2xl border border-line bg-[rgb(19_22_42/0.6)] px-6 py-5 text-muted"
      }
    >
      {children}
    </p>
  )
}
