import { cleanup, fireEvent, render, screen, within } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"
import { GalleryStrips } from "@/components/gallery/gallery-strips"
import type { GalleryItem } from "@/lib/api/types"

function item(id: number, over: Partial<GalleryItem> = {}): GalleryItem {
  return {
    id,
    kind: "image",
    url: `/media/gallery/${id}.png`,
    provider: null,
    caption: `Souvenir ${id}`,
    author: { id: String(100 + id), name: `Membre ${id}`, avatar: null },
    created_at: "2026-11-15T20:00:00Z",
    ...over,
  }
}

afterEach(cleanup)

/** Première vignette visible (hors copie du bandeau) portant `caption`. */
const tile = (caption: string) =>
  screen.getAllByRole("button").find(b => b.textContent?.includes(caption) && !b.closest("[aria-hidden='true']"))!

describe("aperçu agrandi de la galerie", () => {
  it("Échap ferme l'aperçu et rend le focus à la vignette", () => {
    render(<GalleryStrips items={[item(1), item(2), item(3)]} />)
    const trigger = tile("Souvenir 2")
    trigger.focus()
    fireEvent.click(trigger)

    const dialog = screen.getByRole("dialog", { name: "Souvenir 2" })
    expect(within(dialog).getByText("Membre 2")).toBeTruthy()
    // Focus sur « Fermer », pas sur un lecteur intégré qui avalerait Échap.
    expect(document.activeElement).toBe(within(dialog).getByRole("button", { name: "Fermer" }))

    fireEvent.keyDown(dialog, { key: "Escape" })
    expect(screen.queryByRole("dialog")).toBeNull()
    expect(document.activeElement).toBe(trigger)
  })

  it("un clic hors du cadre ferme, un clic dans le cadre non", () => {
    render(<GalleryStrips items={[item(1), item(2)]} />)
    const trigger = tile("Souvenir 1")
    fireEvent.click(trigger)
    const dialog = screen.getByRole("dialog")

    fireEvent.click(within(dialog).getByText("Membre 1"))
    expect(screen.getByRole("dialog")).toBeTruthy()

    fireEvent.click(dialog) // la toile de fond : la cible est le <dialog> lui-même
    expect(screen.queryByRole("dialog")).toBeNull()
    expect(document.activeElement).toBe(trigger)
  })

  it("le bouton Fermer ferme et rend le focus", () => {
    render(<GalleryStrips items={[item(1)]} />)
    const trigger = tile("Souvenir 1")
    fireEvent.click(trigger)
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Fermer" }))
    expect(screen.queryByRole("dialog")).toBeNull()
    expect(document.activeElement).toBe(trigger)
  })
})
