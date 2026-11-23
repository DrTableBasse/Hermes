"use client"

import { useState } from "react"
import type { UserSearchResult } from "@/lib/api/types"
import { AdminLogs } from "./admin-logs"
import { MemberInspector } from "./member-inspector"
import { ModerationActions } from "./moderation-actions"
import { WarnsList } from "./warns-list"

/** Modération : sanction, fiche d'un membre, sanctions du serveur, journal. */
export function ModerationPanel() {
  const [target, setTarget] = useState<UserSearchResult | null>(null)
  // Incrémenté après chaque sanction : la fiche et la liste se relisent.
  const [revision, setRevision] = useState(0)

  return (
    <div className="grid gap-6">
      <ModerationActions target={target} onTarget={setTarget} onDone={() => setRevision(r => r + 1)} />
      <div className="grid gap-6 lg:grid-cols-2">
        <MemberInspector refreshKey={revision} onSanction={setTarget} />
        <WarnsList refreshKey={revision} />
      </div>
      <AdminLogs key={revision} />
    </div>
  )
}
