"use client"

import { useEffect, useId, useState } from "react"
import { Avatar } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import { Panel } from "@/components/ui/panel"
import { api } from "@/lib/api/client"
import type { UserSearchResult, UserStats, Warn } from "@/lib/api/types"
import { formatNumber } from "@/lib/format"
import { ConfirmButton } from "./confirm-button"
import { adminErrorText } from "./form"
import { UserSearchInput } from "./user-search-input"
import { warnDate } from "./warns-list"

/** Lecture étiquetée par `for` (membre et révision) : une étiquette périmée vaut « chargement ». */
type Loaded = { for: string } & ({ status: "error"; text: string } | { status: "ok"; profile: UserStats; warns: Warn[] })

type Props = {
  /** `id` de la section : cible des liens « auteur » / « cible » du journal. */
  id?: string
  /** Membre ouvert (contrôlé par le parent, que le journal peut aussi changer). */
  member: UserSearchResult | null
  onMember: (user: UserSearchResult | null) => void
  /** Change à chaque sanction réussie : la fiche ouverte est relue. */
  refreshKey: number
  onSanction: (user: UserSearchResult) => void
}

/** Fiche d'un membre : statistiques, sanctions (supprimables après confirmation), succès. */
export function MemberInspector({ id, member, onMember, refreshKey, onSanction }: Props) {
  const ids = useId()
  const [loaded, setLoaded] = useState<Loaded | null>(null)
  const [warnError, setWarnError] = useState<string | null>(null)
  const tag = member ? `${member.user_id}:${refreshKey}` : null

  useEffect(() => {
    if (!member || !tag) return
    let alive = true
    Promise.all([api.users.stats(member.user_id), api.admin.getWarns(member.user_id)])
      .then(([profile, warns]) => alive && setLoaded({ for: tag, status: "ok", profile, warns: warns.warns }))
      .catch(e => alive && setLoaded({ for: tag, status: "error", text: adminErrorText(e) }))
    return () => {
      alive = false
    }
  }, [member, tag])

  const data = loaded && loaded.for === tag ? loaded : null

  async function removeWarn(id: number) {
    setWarnError(null)
    try {
      await api.admin.deleteWarn(id)
      setLoaded(d => (d && d.status === "ok" ? { ...d, warns: d.warns.filter(w => w.id !== id) } : d))
    } catch (e) {
      setWarnError(adminErrorText(e))
    }
  }

  return (
    <Panel as="section" id={id} tabIndex={-1} aria-labelledby={`${ids}-title`} className="grid scroll-mt-24 gap-5">
      <h2 id={`${ids}-title`} className="m-0 font-display text-xl font-extrabold">
        Fiche d’un membre
      </h2>
      <div className="max-w-sm">
        <UserSearchInput
          label="Rechercher un membre"
          selected={member}
          onSelect={onMember}
          onClear={() => onMember(null)}
        />
      </div>
      {member && !data && <p className="m-0 text-sm text-muted">Chargement…</p>}
      {data?.status === "error" && (
        <p role="alert" className="m-0 text-sm text-orange">
          {data.text}
        </p>
      )}
      {data?.status === "ok" && member && (
        <div className="grid gap-5">
          <div className="flex flex-wrap items-center gap-4">
            <Avatar name={data.profile.user.username} src={data.profile.user.discord_avatar} size={56} />
            <div className="min-w-0">
              <p className="m-0 text-lg font-semibold">{data.profile.user.nickname ?? data.profile.user.username}</p>
              <p className="m-0 font-mono text-xs text-muted">ID {member.user_id}</p>
            </div>
            <Button size="sm" variant="ghost" className="ml-auto" onClick={() => onSanction(member)}>
              Sanctionner
            </Button>
          </div>
          <dl className="m-0 grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[
              ["Messages", `${formatNumber(data.profile.stats.total_messages)} (#${data.profile.stats.msg_rank})`],
              ["Vocal", `${formatNumber(Math.floor(data.profile.stats.voice_hours))} h (#${data.profile.stats.voice_rank})`],
              ["Niveau", `${data.profile.stats.current_level} · ${formatNumber(data.profile.stats.xp_total)} XP`],
              ["Sanctions", String(data.warns.length)],
            ].map(([label, value]) => (
              <div key={label} className="rounded-xl border border-line px-3 py-2.5">
                <dt className="text-xs text-muted">{label}</dt>
                <dd className="m-0 font-semibold tabular-nums">{value}</dd>
              </div>
            ))}
          </dl>
          <div className="grid gap-2">
            <h3 className="m-0 text-sm font-semibold text-muted">Sanctions ({data.warns.length})</h3>
            {warnError && (
              <p role="alert" className="m-0 text-sm text-orange">
                {warnError}
              </p>
            )}
            {data.warns.length === 0 ? (
              <p className="m-0 text-sm text-muted">Aucune sanction enregistrée.</p>
            ) : (
              <ul className="m-0 grid list-none gap-2 p-0">
                {data.warns.map(w => (
                  <li key={w.id} className="flex flex-wrap items-start justify-between gap-3 rounded-xl border border-line px-4 py-3">
                    <div className="min-w-0">
                      <p className="m-0 text-sm font-medium">{w.reason}</p>
                      <p className="m-0 text-xs text-muted">
                        {warnDate(w.create_time)} · par {w.moderator_username ?? `#${w.moderator_id}`}
                      </p>
                    </div>
                    <ConfirmButton question="Retirer cette sanction ?" confirmLabel="Retirer" onConfirm={() => removeWarn(w.id)}>
                      Retirer
                    </ConfirmButton>
                  </li>
                ))}
              </ul>
            )}
          </div>
          {data.profile.achievements.length > 0 && (
            <p className="m-0 text-sm text-muted">
              {data.profile.achievements.length} succès débloqué{data.profile.achievements.length > 1 ? "s" : ""} :{" "}
              {data.profile.achievements.map(a => a.name).join(", ")}.
            </p>
          )}
        </div>
      )}
    </Panel>
  )
}
