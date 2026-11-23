"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Chip } from "@/components/ui/chip"
import { api } from "@/lib/api/client"
import type { AdminGalleryItem } from "@/lib/api/types"
import { cn } from "@/lib/cn"
import { formatDate } from "@/lib/format"
import { ConfirmButton } from "./confirm-button"
import { adminErrorText } from "./form"

type Status = { id: number; kind: "ok" | "error"; text: string } | null

/** Modération de la galerie : masquer / réafficher, supprimer après confirmation. */
export function GalleryModeration({ items: initial }: { items: AdminGalleryItem[] }) {
  const [items, setItems] = useState(initial)
  const [busy, setBusy] = useState<number | null>(null)
  const [status, setStatus] = useState<Status>(null)

  async function run(id: number, action: () => Promise<void>, done: string) {
    setBusy(id)
    setStatus(null)
    try {
      await action()
      setStatus({ id, kind: "ok", text: done })
    } catch (e) {
      setStatus({ id, kind: "error", text: adminErrorText(e) })
    } finally {
      setBusy(null)
    }
  }

  const setHidden = (item: AdminGalleryItem) =>
    run(
      item.id,
      async () => {
        const res = await api.admin.setGalleryHidden(item.id, !item.hidden)
        setItems(list => list.map(i => (i.id === item.id ? { ...i, hidden: res.hidden } : i)))
      },
      item.hidden ? "Élément de nouveau visible." : "Élément masqué du site.",
    )

  const remove = (item: AdminGalleryItem) =>
    run(
      item.id,
      async () => {
        await api.admin.deleteGalleryItem(item.id)
        setItems(list => list.filter(i => i.id !== item.id))
      },
      "Élément supprimé.",
    )

  if (items.length === 0) return <p className="m-0 text-muted">La galerie est vide.</p>

  return (
    <div className="grid gap-3">
      {status && !items.some(i => i.id === status.id) && (
        <p role="status" className="m-0 text-sm text-green">
          {status.text}
        </p>
      )}
      <ul className="m-0 grid list-none gap-4 p-0 sm:grid-cols-2 lg:grid-cols-3">
        {items.map(item => {
          const title = item.caption || (item.kind === "clip" ? `Clip ${item.provider ?? ""}`.trim() : "Image")
          return (
            <li
              key={item.id}
              className={cn(
                "grid content-start gap-3 rounded-[20px] border bg-[rgb(19_22_42/0.92)] p-4",
                item.hidden ? "border-orange/30" : "border-line",
              )}
            >
              {item.kind === "image" && item.url ? (
                // eslint-disable-next-line @next/next/no-img-element -- vignette de modération, fichier local
                <img
                  src={item.url}
                  alt={item.caption ?? ""}
                  loading="lazy"
                  className={cn("aspect-video w-full rounded-xl object-cover", item.hidden && "opacity-50")}
                />
              ) : (
                <a
                  href={item.url ?? undefined}
                  target="_blank"
                  rel="noopener noreferrer nofollow"
                  className="grid aspect-video place-items-center rounded-xl border border-line bg-white/4 text-sm font-semibold text-cyan hover:underline"
                >
                  Ouvrir le clip {item.provider ?? ""} (nouvel onglet)
                </a>
              )}
              <div className="grid gap-1">
                <p className="m-0 truncate font-semibold">{title}</p>
                <p className="m-0 text-sm text-muted">
                  {item.author.name}
                  {item.created_at ? ` · ${formatDate(item.created_at)}` : ""}
                </p>
                {item.hidden && <Chip color="var(--color-orange)">Masqué</Chip>}
              </div>
              <div className="flex flex-wrap gap-2">
                <Button size="sm" variant="ghost" disabled={busy !== null} onClick={() => void setHidden(item)}>
                  {item.hidden ? "Afficher" : "Masquer"}
                </Button>
                <ConfirmButton
                  question="Supprimer définitivement ?"
                  confirmLabel="Supprimer"
                  disabled={busy !== null}
                  onConfirm={() => remove(item)}
                >
                  Supprimer
                </ConfirmButton>
              </div>
              {status?.id === item.id && (
                <p role={status.kind === "error" ? "alert" : "status"} className={cn("m-0 text-sm", status.kind === "error" ? "text-orange" : "text-green")}>
                  {status.text}
                </p>
              )}
            </li>
          )
        })}
      </ul>
    </div>
  )
}
