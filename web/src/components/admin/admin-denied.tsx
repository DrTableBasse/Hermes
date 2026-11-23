import { Button } from "@/components/ui/button"
import { Panel } from "@/components/ui/panel"
import type { AdminGate } from "@/lib/admin-gate"

/** Accès refusé (403) ou vérification impossible : page propre, sans rien des outils d'administration. */
export function AdminDenied({ gate }: { gate: Exclude<AdminGate, { kind: "ok" }> }) {
  const forbidden = gate.kind === "forbidden"
  return (
    <div className="relative pt-6 pb-24">
      <div className="mx-auto max-w-[640px]">
        <Panel className="grid gap-4 text-center">
          <p className="m-0 font-mono text-sm text-muted">{forbidden ? "Erreur 403" : "Vérification impossible"}</p>
          <h1 className="m-0 font-display text-3xl font-extrabold">
            {forbidden ? "Zone réservée à l’administration" : "Impossible de vérifier tes droits"}
          </h1>
          <p className="m-0 text-muted">
            {forbidden
              ? "Ton compte n’a pas le rôle d’administration sur le serveur. Si c’est une erreur, demande-le à un admin puis reconnecte-toi."
              : "Le site ne répond pas pour l’instant. Réessaie dans un moment."}
          </p>
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
