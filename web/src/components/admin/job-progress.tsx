"use client"

import { useEffect, useState } from "react"
import { api, ApiError } from "@/lib/api/client"
import type { RoleJob } from "@/lib/api/types"
import { JOB_POLL_MS, jobIsAlarming, jobText } from "@/lib/jobs"
import { adminErrorText } from "./form"

type Props = {
  jobId: string
  /** Nom accessible de l'annonce (« Suivi du lot », « Application de la règle »). */
  label: string
  /** Appelé une fois, quand le travail ne tourne plus (terminé, interrompu, échec, perdu). */
  onSettled?: () => void
}

type Track = { job: RoleJob | null; lost: boolean; error: string | null }

/**
 * Suivi d'un travail du bot (`GET /admin/jobs/{id}`) : relevé immédiat puis toutes les
 * `JOB_POLL_MS` tant qu'il tourne. Un 404 (bot redémarré, suivi expiré) vaut « interrompu ».
 */
export function JobProgress({ jobId, label, onSettled }: Props) {
  const [track, setTrack] = useState<Track>({ job: null, lost: false, error: null })

  useEffect(() => {
    let alive = true
    let timer: ReturnType<typeof setTimeout> | undefined
    let last: RoleJob | null = null
    const settle = (next: Track) => {
      setTrack(next)
      onSettled?.()
    }
    async function poll() {
      try {
        const job = await api.admin.job(jobId)
        if (!alive) return
        last = job
        if (job.state === "running") {
          setTrack({ job, lost: false, error: null })
          timer = setTimeout(() => void poll(), JOB_POLL_MS)
        } else settle({ job, lost: false, error: null })
      } catch (e) {
        if (!alive) return
        if (e instanceof ApiError && e.status === 404) settle({ job: last, lost: true, error: null })
        else settle({ job: last, lost: false, error: `Suivi impossible : ${adminErrorText(e)}` })
      }
    }
    void poll()
    return () => {
      alive = false
      clearTimeout(timer)
    }
    // `onSettled` n'est lu qu'à la fin : le suivi ne repart pas quand le parent change de rappel.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId])

  if (track.error || jobIsAlarming(track.job, track.lost)) {
    return (
      <p role="alert" aria-label={label} className="m-0 text-sm text-orange">
        {track.error ?? jobText(track.job, track.lost)}
      </p>
    )
  }
  return (
    <p role="status" aria-label={label} className={track.job?.state === "done" ? "m-0 text-sm text-green" : "m-0 text-sm text-muted"}>
      {jobText(track.job)}
    </p>
  )
}
