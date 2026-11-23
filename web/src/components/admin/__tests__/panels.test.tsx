import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import type { AdminGalleryItem, AdminGame } from "@/lib/api/types"

const client = vi.hoisted(() => {
  class ApiError extends Error {
    constructor(
      readonly status: number,
      message: string,
    ) {
      super(message)
    }
  }
  const admin = Object.fromEntries(
    [
      "setGalleryHidden", "deleteGalleryItem", "toggleCommand", "createGame", "updateGame", "deactivateGame",
      "updatePage", "updateGrade", "updateStaffProfile", "warn", "kick", "ban", "timeout", "searchUsers",
    ].map(n => [n, vi.fn()]),
  )
  return { api: { admin, media: { upload: vi.fn() } }, ApiError }
})
vi.mock("@/lib/api/client", () => client)

import { CommandsPanel } from "@/components/admin/commands-panel"
import { GalleryModeration } from "@/components/admin/gallery-moderation"
import { GamesAdmin } from "@/components/admin/games-admin"
import { GradesEditor } from "@/components/admin/grades-editor"
import { ModerationActions } from "@/components/admin/moderation-actions"
import { PageEditor } from "@/components/admin/page-editor"
import { StaffEditor } from "@/components/admin/staff-editor"

const a = client.api.admin
const click = async (el: HTMLElement) => {
  await act(async () => {
    fireEvent.click(el)
  })
}
const button = (name: string | RegExp) => screen.getByRole("button", { name })

const image = (id: number, hidden = false): AdminGalleryItem => ({
  id, kind: "image", url: `/media/gallery/${id}.png`, provider: null, caption: `Image ${id}`, hidden,
  author: { id: "2", name: "Zoé", avatar: null }, created_at: null,
})

const game = (key: string, position: number, active = true): AdminGame => ({
  key, name: key.toUpperCase(), color: "#3FA9C9", image: null, tagline: null,
  discord_role_id: null, forum_channel_id: null, position, active,
})

beforeEach(() => {
  vi.spyOn(window, "confirm").mockImplementation(() => {
    throw new Error("window.confirm interdit")
  })
  for (const fn of Object.values(a)) fn.mockResolvedValue({ ok: true })
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  vi.clearAllMocks()
})

describe("GalleryModeration", () => {
  it("masquer puis afficher", async () => {
    a.setGalleryHidden.mockResolvedValueOnce({ id: 1, hidden: true }).mockResolvedValueOnce({ id: 1, hidden: false })
    render(<GalleryModeration items={[image(1)]} />)
    await click(button("Masquer"))
    expect(a.setGalleryHidden).toHaveBeenCalledWith(1, true)
    expect(screen.getByText("Masqué")).toBeTruthy()
    await click(button("Afficher"))
    expect(a.setGalleryHidden).toHaveBeenLastCalledWith(1, false)
    expect(screen.queryByText("Masqué")).toBeNull()
  })

  it("supprimer : confirmation dans la page, Annuler n’envoie rien", async () => {
    render(<GalleryModeration items={[image(1), image(2)]} />)
    const first = screen.getAllByRole("listitem")[0]
    await click(within(first).getByRole("button", { name: "Supprimer" }))
    expect(within(first).getByRole("group", { name: "Supprimer définitivement ?" })).toBeTruthy()
    await click(within(first).getByRole("button", { name: "Annuler" }))
    expect(a.deleteGalleryItem).not.toHaveBeenCalled()
    vi.useFakeTimers({ toFake: ["Date"] })
    try {
      await click(within(first).getByRole("button", { name: "Supprimer" }))
      vi.setSystemTime(Date.now() + 400) // au-delà de la garde anti double activation
      await click(within(first).getAllByRole("button", { name: "Supprimer" })[0])
    } finally {
      vi.useRealTimers()
    }
    expect(a.deleteGalleryItem).toHaveBeenCalledWith(1)
    expect(screen.getAllByRole("listitem")).toHaveLength(1)
    expect(screen.getByRole("status").textContent).toBe("Élément supprimé.")
  })

  it("erreur de l’API affichée sur l’élément, état inchangé", async () => {
    a.setGalleryHidden.mockRejectedValue(new client.ApiError(404, "Élément introuvable"))
    render(<GalleryModeration items={[image(1)]} />)
    await click(button("Masquer"))
    expect(screen.getByRole("alert").textContent).toMatch(/Élément introuvable/)
    expect(screen.queryByText("Masqué")).toBeNull()
  })
})

describe("CommandsPanel", () => {
  it("bascule une commande, puis la remet", async () => {
    render(<CommandsPanel commands={{ rank: true }} descriptions={{}} />)
    const sw = screen.getByRole("switch", { name: "/rank" })
    await click(sw)
    expect(a.toggleCommand).toHaveBeenCalledWith({ command_name: "rank", enabled: false })
    expect(sw.getAttribute("aria-checked")).toBe("false")
    await click(sw)
    expect(a.toggleCommand).toHaveBeenLastCalledWith({ command_name: "rank", enabled: true })
    expect(sw.getAttribute("aria-checked")).toBe("true")
  })

  it("échec : état conservé, erreur annoncée", async () => {
    a.toggleCommand.mockRejectedValue(new client.ApiError(502, "Bot injoignable"))
    render(<CommandsPanel commands={{ rank: true }} descriptions={{}} />)
    await click(screen.getByRole("switch", { name: "/rank" }))
    expect(screen.getByRole("switch", { name: "/rank" }).getAttribute("aria-checked")).toBe("true")
    expect(screen.getByRole("alert").textContent).toMatch(/\/rank : Hermes \(le bot\) ne répond pas/)
  })
})

describe("GamesAdmin", () => {
  it("ajout d’un jeu : clé, couleur, accroche, position suivante", async () => {
    render(<GamesAdmin games={[game("lol", 4)]} roles={[{ id: "20", name: "LoL", color: 0 }]} channels={null} />)
    await click(button("Ajouter un jeu"))
    fireEvent.change(screen.getByLabelText("Clé (définitive)"), { target: { value: "Apex" } })
    fireEvent.change(screen.getByLabelText("Nom"), { target: { value: " Apex Legends " } })
    fireEvent.change(screen.getByLabelText("Couleur"), { target: { value: "#aabbcc" } })
    fireEvent.change(screen.getByLabelText("Accroche"), { target: { value: "Tombe, relève-toi." } })
    fireEvent.change(screen.getByLabelText("Rôle Discord"), { target: { value: "20" } })
    await click(button("Ajouter le jeu"))
    expect(a.createGame).toHaveBeenCalledWith(
      expect.objectContaining({ key: "apex", name: "Apex Legends", color: "#aabbcc", tagline: "Tombe, relève-toi.", discord_role_id: "20", position: 5 }),
    )
    expect(screen.getByRole("status").textContent).toMatch(/ajouté/)
  })

  it("couleur invalide : envoi bloqué", async () => {
    render(<GamesAdmin games={[]} roles={null} channels={null} />)
    await click(button("Ajouter un jeu"))
    fireEvent.change(screen.getByLabelText("Clé (définitive)"), { target: { value: "x" } })
    fireEvent.change(screen.getByLabelText("Nom"), { target: { value: "X" } })
    fireEvent.change(screen.getByLabelText("Couleur"), { target: { value: "rouge" } })
    expect(screen.getByText("Couleur au format #RRGGBB.")).toBeTruthy()
    expect((button("Ajouter le jeu") as HTMLButtonElement).disabled).toBe(true)
  })

  it("ordre : descendre échange et renumérote ; désactiver puis réactiver", async () => {
    render(<GamesAdmin games={[game("b", 7), game("a", 3)]} roles={null} channels={null} />)
    await click(button("Descendre A"))
    expect(a.updateGame).toHaveBeenCalledWith("b", { position: 1 })
    expect(a.updateGame).toHaveBeenCalledWith("a", { position: 2 })
    expect(screen.getAllByRole("listitem").map(li => li.querySelector("p")?.firstChild?.textContent)).toEqual(["B", "A"])
    await click(screen.getAllByRole("button", { name: "Désactiver" })[0])
    expect(a.deactivateGame).toHaveBeenCalledWith("b")
    expect(screen.getByText("Désactivé")).toBeTruthy()
    await click(button("Réactiver"))
    expect(a.updateGame).toHaveBeenLastCalledWith("b", { active: true })
  })
})

describe("PageEditor", () => {
  it("aperçu Markdown sûr : le HTML brut reste du texte", async () => {
    render(<PageEditor page={{ slug: "reglement", title: "Règlement", body_md: "", updated_at: null }} />)
    fireEvent.change(screen.getByLabelText("Contenu (Markdown)"), {
      target: { value: "## Article 1\n\n<img src=x onerror=alert(1)><script>alert(1)</script>" },
    })
    await click(button("Aperçu"))
    const preview = screen.getByLabelText("Aperçu")
    expect(within(preview).getByRole("heading", { level: 2, name: "Article 1" })).toBeTruthy()
    expect(preview.querySelector("script, img")).toBeNull()
    expect(preview.textContent).toContain("<script>")
  })

  it("enregistre titre et contenu ; refuse au-delà de 50 000 caractères", async () => {
    render(<PageEditor page={{ slug: "mentions-legales", title: "Mentions", body_md: "Texte", updated_at: null }} />)
    await click(button("Enregistrer"))
    expect(a.updatePage).toHaveBeenCalledWith("mentions-legales", { title: "Mentions", body_md: "Texte" })
    expect(screen.getByRole("status").textContent).toMatch(/Enregistré/)
    fireEvent.change(screen.getByLabelText("Contenu (Markdown)"), { target: { value: "a".repeat(50_001) } })
    expect((button("Enregistrer") as HTMLButtonElement).disabled).toBe(true)
  })
})

describe("GradesEditor", () => {
  const GRADES = [
    { name: "Caporal", slug: "caporal", color: "#3FA9C9", level_min: 10 },
    { name: "Recrue", slug: "recrue", color: "#AAAAAA", level_min: 1 },
  ]

  it("recrue : niveau 1 verrouillé ; les grades sont triés par niveau", () => {
    render(<GradesEditor grades={GRADES} />)
    const forms = screen.getAllByRole("form")
    expect(forms[0].getAttribute("aria-label")).toBe("Grade Recrue")
    expect((within(forms[0]).getByLabelText("Niveau minimal") as HTMLInputElement).readOnly).toBe(true)
    expect(screen.getByText("Premier grade : niveau 1 fixe.")).toBeTruthy()
  })

  it("enregistre nom, couleur et niveau ; 409 de l’API affiché sur la ligne", async () => {
    a.updateGrade.mockRejectedValueOnce(new client.ApiError(409, "Un autre grade commence déjà à ce niveau"))
    render(<GradesEditor grades={GRADES} />)
    const caporal = screen.getByRole("form", { name: "Grade Caporal" })
    fireEvent.change(within(caporal).getByLabelText("Niveau minimal"), { target: { value: "1" } })
    await click(within(caporal).getByRole("button", { name: "Enregistrer" }))
    expect(a.updateGrade).toHaveBeenCalledWith("caporal", { name: "Caporal", color: "#3FA9C9", level_min: 1 })
    expect(within(caporal).getByRole("alert").textContent).toMatch(/Un autre grade commence déjà/)
  })
})

describe("StaffEditor", () => {
  const STAFF = [{ id: "7", name: "Kéfir", avatar: null, role: "Modo", grade: null, level: null, motto: null, games: ["lol"] }]
  const GAMES = [{ key: "lol", name: "LoL", color: "#F5A623", image: null, tagline: null, players: null, forum_url: null }]

  it("enregistre phrase et jeux du membre par son identifiant", async () => {
    render(<StaffEditor staff={STAFF} games={GAMES} />)
    fireEvent.change(screen.getByLabelText("Phrase de Kéfir"), { target: { value: "  Je veille.  " } })
    fireEvent.click(screen.getByRole("checkbox", { name: "LoL" }))
    await click(button("Enregistrer"))
    expect(a.updateStaffProfile).toHaveBeenCalledWith("7", { motto: "Je veille.", games: [] })
    expect(screen.getByRole("status").textContent).toMatch(/Enregistré/)
  })

  it("membre sorti de l’état-major (404) : erreur lisible", async () => {
    a.updateStaffProfile.mockRejectedValue(new client.ApiError(404, "Membre absent de l'état-major"))
    render(<StaffEditor staff={STAFF} games={GAMES} />)
    await click(button("Enregistrer"))
    expect(screen.getByRole("alert").textContent).toMatch(/Membre absent/)
  })
})

describe("ModerationActions", () => {
  const TARGET = { user_id: "42", username: "Fauteur", discord_avatar: null }

  it("bannir exige une confirmation dans la page ; Échap annule sans rien envoyer", async () => {
    render(<ModerationActions target={TARGET} onTarget={vi.fn()} onDone={vi.fn()} />)
    await click(button("Bannir"))
    const group = screen.getByRole("group", { name: "Bannir Fauteur définitivement ?" })
    // Focus sur « Annuler », jamais sur l'action destructive.
    expect(document.activeElement).toBe(within(group).getByRole("button", { name: "Annuler" }))
    fireEvent.keyDown(group, { key: "Escape" })
    expect(screen.queryByRole("group")).toBeNull()
    expect(a.ban).not.toHaveBeenCalled()
    expect(document.activeElement).toBe(button("Bannir"))
  })

  it("deux Entrée sur « Bannir » → ban non appelé", async () => {
    render(<ModerationActions target={TARGET} onTarget={vi.fn()} onDone={vi.fn()} />)
    // Entrée sur un bouton = activation de l'élément qui a le focus.
    const trigger = button("Bannir")
    trigger.focus()
    await click(document.activeElement as HTMLElement)
    await click(document.activeElement as HTMLElement)
    expect(a.ban).not.toHaveBeenCalled()
    expect(screen.queryByRole("group")).toBeNull()
  })

  it("confirmation ignorée pendant 400 ms après l'ouverture, puis acceptée avec le bon corps", async () => {
    vi.useFakeTimers({ toFake: ["Date"] })
    try {
      render(<ModerationActions target={TARGET} onTarget={vi.fn()} onDone={vi.fn()} />)
      fireEvent.change(screen.getByLabelText("Durée (min)"), { target: { value: "30" } })
      await click(button("Exclure temporairement"))
      const group = screen.getByRole("group", { name: "Exclure Fauteur temporairement ?" })
      await click(within(group).getByRole("button", { name: "Confirmer" }))
      expect(a.timeout).not.toHaveBeenCalled()
      vi.setSystemTime(Date.now() + 399)
      await click(within(group).getByRole("button", { name: "Confirmer" }))
      expect(a.timeout).not.toHaveBeenCalled()
      vi.setSystemTime(Date.now() + 1)
      await click(within(group).getByRole("button", { name: "Confirmer" }))
      expect(a.timeout).toHaveBeenCalledWith({ user_id: "42", reason: "Action depuis le site", duration: 30 })
    } finally {
      vi.useRealTimers()
    }
  })

  it("avertir : envoi direct avec la raison ; succès annoncé et fiche relue", async () => {
    const onDone = vi.fn()
    render(<ModerationActions target={TARGET} onTarget={vi.fn()} onDone={onDone} />)
    fireEvent.change(screen.getByLabelText("Raison"), { target: { value: "Spam" } })
    await click(button("Avertir"))
    expect(a.warn).toHaveBeenCalledWith({ user_id: "42", reason: "Spam" })
    expect(onDone).toHaveBeenCalled()
    expect(screen.getByRole("status").textContent).toMatch(/Avertissement enregistré : Fauteur/)
  })

  it("sans membre choisi : toutes les actions désactivées", () => {
    render(<ModerationActions target={null} onTarget={vi.fn()} onDone={vi.fn()} />)
    for (const name of ["Avertir", "Exclure temporairement", "Expulser", "Bannir"]) {
      expect((button(name) as HTMLButtonElement).disabled).toBe(true)
    }
  })
})
