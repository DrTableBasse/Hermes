import { cleanup, fireEvent, render, screen, within } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import type { GalleryItem } from "@/lib/api/types"

const api = vi.hoisted(() => ({ getGallery: vi.fn(), getPublicSettings: vi.fn() }))
vi.mock("@/lib/api/server", () => api)

import GalleryPage from "@/app/[locale]/galerie/page"

const ITEMS: GalleryItem[] = [
  {
    id: 1,
    kind: "image",
    url: "/media/gallery/ace.png",
    provider: null,
    caption: "Ace en 1 contre 5",
    author: { id: "11", name: "Kéfir", avatar: null },
    created_at: "2026-11-15T20:00:00Z",
  },
  {
    id: 2,
    kind: "clip",
    url: "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    provider: "youtube",
    caption: "Le killer qui avait peur du noir",
    author: { id: "12", name: "Merguez_Royale", avatar: null },
    created_at: null,
  },
  {
    id: 3,
    kind: "clip",
    url: "https://clips.twitch.tv/PentakillParErreur",
    provider: "twitch",
    caption: null,
    author: { id: "13", name: "Chipolata", avatar: null },
    created_at: "2026-11-01T18:00:00Z",
  },
]

/** Vignettes atteignables (hors copies et répétitions cachées). */
const visibleTiles = () =>
  within(screen.getByTestId("gallery-strips"))
    .getAllByRole("button")
    .filter(b => !b.closest("[aria-hidden='true']"))

beforeEach(() => {
  api.getGallery.mockResolvedValue({ items: ITEMS })
  api.getPublicSettings.mockResolvedValue({ invite_url: "https://discord.gg/saucisse" })
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe("page /galerie", () => {
  it("deux bandeaux en sens inverse, chaque souvenir une seule fois au clavier", async () => {
    render(await GalleryPage())
    expect(screen.getByRole("heading", { level: 1, name: "Les archives de la caserne" })).toBeTruthy()

    const strips = screen.getAllByRole("region", { name: /^Archives, bande/ })
    expect(strips).toHaveLength(2)
    const directions = strips.map(s => (s.querySelector("[data-marquee-track]") as HTMLElement).style.animationDirection)
    expect(directions).toEqual(["normal", "reverse"])

    expect(visibleTiles().map(b => b.querySelector("b")?.textContent)).toEqual([
      "Ace en 1 contre 5",
      "Souvenir sans légende",
      "Le killer qui avait peur du noir",
    ])
    // Copies et répétitions restent cliquables mais hors tabulation.
    const hidden = within(screen.getByTestId("gallery-strips"))
      .getAllByRole("button", { hidden: true })
      .filter(b => b.closest("[aria-hidden='true']"))
    expect(hidden.length).toBeGreaterThan(0)
    expect(hidden.every(b => b.tabIndex === -1)).toBe(true)
    expect(screen.queryByTestId("gallery-empty")).toBeNull()
  })

  it("aperçu d'un clip YouTube : lecteur youtube-nocookie et lien vers l'URL canonique", async () => {
    render(await GalleryPage())
    fireEvent.click(visibleTiles()[2])
    const dialog = screen.getByRole("dialog", { name: "Le killer qui avait peur du noir" })
    const frame = dialog.querySelector("iframe")!
    expect(frame.getAttribute("src")).toBe("https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ")
    expect(within(dialog).getByRole("link", { name: "Voir sur YouTube" }).getAttribute("href")).toBe(
      "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    )
  })

  it("aperçu d'un clip Twitch : parent = hôte courant", async () => {
    render(await GalleryPage())
    fireEvent.click(visibleTiles()[1])
    const frame = screen.getByRole("dialog").querySelector("iframe")!
    expect(frame.getAttribute("src")).toBe(
      `https://clips.twitch.tv/embed?clip=PentakillParErreur&parent=${window.location.hostname}`,
    )
  })

  it("vignette d'une capture : miniature de l'optimiseur, jamais l'original", async () => {
    render(await GalleryPage())
    const src = visibleTiles()[0].querySelector("img")!.getAttribute("src")!
    expect(src.startsWith("/_next/image?url=%2Fmedia%2Fgallery%2Face.png&w=")).toBe(true)
    // Miniature YouTube : déjà légère, lue chez le fournisseur.
    expect(visibleTiles()[2].querySelector("img")!.getAttribute("src")).toBe(
      "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg",
    )
  })

  it("aperçu d'une capture : l'image, sans lecteur", async () => {
    render(await GalleryPage())
    fireEvent.click(visibleTiles()[0])
    const dialog = screen.getByRole("dialog", { name: "Ace en 1 contre 5" })
    expect(within(dialog).getByRole("img", { name: "Ace en 1 contre 5" }).getAttribute("src")).toBe("/media/gallery/ace.png")
    expect(dialog.querySelector("iframe")).toBeNull()
    expect(within(dialog).getByText(/15 novembre 2026/)).toBeTruthy()
  })

  it("galerie vide : invitation à poster dans #galerie, sans bandeau", async () => {
    api.getGallery.mockResolvedValue({ items: [] })
    render(await GalleryPage())
    const empty = screen.getByTestId("gallery-empty")
    expect(within(empty).getByText((_, el) => el?.textContent === "Poste tes meilleurs moments dans #galerie")).toBeTruthy()
    expect(within(empty).getByRole("link", { name: "Ouvrir le Discord" }).getAttribute("href")).toBe("https://discord.gg/saucisse")
    expect(screen.queryByTestId("gallery-strips")).toBeNull()
  })

  it("API indisponible : message d'indisponibilité, ni bandeau ni invitation", async () => {
    api.getGallery.mockResolvedValue(null)
    api.getPublicSettings.mockResolvedValue(null)
    render(await GalleryPage())
    expect(screen.getByRole("status").textContent).toMatch(/injoignables/)
    expect(screen.queryByTestId("gallery-strips")).toBeNull()
    expect(screen.queryByTestId("gallery-empty")).toBeNull()
  })
})
