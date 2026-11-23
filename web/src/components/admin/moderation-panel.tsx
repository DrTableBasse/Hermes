"use client"

import { Suspense, useState } from "react"
import type { UserSearchResult } from "@/lib/api/types"
import { AuditJournal } from "./audit-journal"
import { MemberInspector } from "./member-inspector"
import { ModerationActions } from "./moderation-actions"
import { WarnsList } from "./warns-list"

/** Modération : sanction, fiche d'un membre, sanctions du serveur, journal. */
/** Ancre de la fiche membre (une seule par page) : cible des liens du journal. */
const INSPECTOR_ID = "fiche-membre"

/** `canAct` faux (droit `moderation.act` absent) : consultation seule, aucune action de sanction. */
export function ModerationPanel({ canAct }: { canAct: boolean }) {
  const [target, setTarget] = useState<UserSearchResult | null>(null)
  // Membre ouvert dans la fiche : choisi dans la fiche ou depuis un lien du journal.
  const [inspected, setInspected] = useState<UserSearchResult | null>(null)
  // Incrémenté après chaque sanction : la fiche, la liste et le journal se relisent.
  const [revision, setRevision] = useState(0)

  return (
    <div className="grid gap-6">
      {canAct ? (
        <ModerationActions target={target} onTarget={setTarget} onDone={() => setRevision(r => r + 1)} />
      ) : (
        <p className="text-sm text-muted">Vous pouvez consulter la modération, pas sanctionner.</p>
      )}
      <div className="grid gap-6 lg:grid-cols-2">
        <MemberInspector
          id={INSPECTOR_ID}
          member={inspected}
          onMember={setInspected}
          refreshKey={revision}
          onSanction={canAct ? setTarget : undefined}
        />
        <WarnsList refreshKey={revision} canAct={canAct} />
      </div>
      <Suspense>
        <AuditJournal key={revision} onInspect={setInspected} inspectorId={INSPECTOR_ID} />
      </Suspense>
    </div>
  )
}
