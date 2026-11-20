import { cleanup, render, screen, within } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"
import { Events } from "@/components/home/events"
import { FinalCta } from "@/components/home/final-cta"
import { GalleryPreview } from "@/components/home/gallery-preview"
import { GradesTimeline } from "@/components/home/grades-timeline"
import { RangDemo } from "@/components/home/rang-demo"
import type { DiscordEvent, GalleryItem, Grade, HermesStatus, LiveState } from "@/lib/api/types"

afterEach(cleanup)

// ── Données d'exemple, de la forme renvoyée par web-api ──

const GRADES: Grade[] = [
  { name: "Caporal Chipolata", slug: "caporal-chipolata", color: "#4D7CFF", level_min: 3 },
  { name: "Recrue Cocktail", slug: "recrue-cocktail", color: "#9A97B8", level_min: 1 },
  { name: "Sergent Merguez", slug: "sergent-merguez", color: "#9B6BFF", level_min: 8 },
  { name: "Lieutenant Toulouse", slug: "lieutenant-toulouse", color: "#3FE0F0", level_min: 15 },
  { name: "Colonel Saucisson", slug: "colonel-saucisson", color: "#F2C14E", level_min: 25 },
  { name: "Général Saucisse", slug: "general-saucisse", color: "#FF8A3D", level_min: 45 },
]

const event = (id: string, name: string, start: string, extra: Partial<DiscordEvent> = {}): DiscordEvent => ({
  id,
  name,
  description: null,
  start,
  end: null,
  status: "scheduled",
  location: null,
  user_count: null,
  creator_id: null,
  image: null,
  url: `https://discord.com/events/1/${id}`,
  xp_reward: null,
  organizer: null,
  ...extra,
})

// Dates lointaines : le compte à rebours ne passe jamais à « C'est parti » pendant le test.
const EVENTS: DiscordEvent[] = [
  event("3", "Clash LoL inter-grades", "2099-11-26T20:00:00Z"),
  event("1", "Soirée killer : Dead by Daylight", "2099-11-21T20:00:00Z", {
    location: "Cantine des Généraux",
    user_count: 14,
    xp_reward: 200,
    organizer: {
      id: "42",
      name: "Merguez_Royale",
      avatar: null,
      grade: { name: "Colonel Saucisson", slug: "colonel-saucisson", color: "#F2C14E" },
    },
  }),
  event("2", "Tournoi Fortnite des Généraux", "2099-11-22T19:00:00Z", { user_count: 18, xp_reward: 300 }),
]

const LIVE: LiveState = {
  members: 1240,
  online: 312,
  in_voice: 37,
  voice_avatars: [],
  game_players: {},
  stale: false,
  updated_at: "2026-11-20T20:09:30Z",
  messages_today: 4812,
  curve_24h: [],
}

const HERMES: HermesStatus = {
  online: true,
  latency_ms: 42.4,
  availability: { percent: 99.97, since: "2026-10-01T00:00:00Z" },
  commands_served: 12400,
  today: { xp_distributed: null, achievements: 3, tickets: 1, bump_reminders: null },
  daily_curve: [],
}

const moment = (id: number, extra: Partial<GalleryItem> = {}): GalleryItem => ({
  id,
  kind: "image",
  url: `/media/gallery/${id}.webp`,
  provider: null,
  caption: `Moment ${id}`,
  author: { id: String(id), name: `Auteur ${id}`, avatar: null },
  created_at: "2026-11-19T20:00:00Z",
  ...extra,
})

const INVITE = "https://discord.gg/saucisseland"

// ── Events ──

describe("Events", () => {
  it("met en vedette le plus proche : compte à rebours, organisateur gradé, intéressés, XP et « Je viens »", () => {
    render(<Events data={{ events: EVENTS }} />)
    expect(screen.getByRole("heading", { name: "Les prochaines manœuvres" })).toBeTruthy()

    const featured = screen.getByTestId("featured-event")
    expect(within(featured).getByText("Prochain event")).toBeTruthy()
    expect(within(featured).getByRole("heading", { level: 3 }).textContent).toBe("Soirée killer : Dead by Daylight")
    expect(within(featured).getByText("Samedi 21 novembre, 21 h")).toBeTruthy()
    expect(within(featured).getByText("Cantine des Généraux")).toBeTruthy()
    expect(within(featured).getByRole("timer")).toBeTruthy()
    expect(featured.textContent).toContain("Organisé par Merguez_Royale")
    expect(featured.querySelector("[data-grade=colonel-saucisson]")?.textContent).toBe("Colonel Saucisson")
    expect(within(featured).getByText("14 intéressés")).toBeTruthy()
    expect(within(featured).getByText("+200 XP pour les participants")).toBeTruthy()
    expect(within(featured).getByRole("link", { name: "Je viens" }).getAttribute("href")).toBe("https://discord.com/events/1/1")
  })

  it("liste les suivants dans l'ordre chronologique, sans chiffre inventé", () => {
    render(<Events data={{ events: EVENTS }} />)
    const list = screen.getByRole("list", { name: "Events suivants" })
    const rows = within(list).getAllByRole("listitem")
    expect(rows.map(r => within(r).getByRole("heading", { level: 4 }).textContent)).toEqual([
      "Tournoi Fortnite des Généraux",
      "Clash LoL inter-grades",
    ])
    expect(rows[0].textContent).toContain("DIM22")
    expect(rows[0].textContent).toContain("20 h.")
    expect(rows[0].textContent).toContain("18 intéressés")
    expect(rows[0].textContent).toContain("+300 XP")
    // user_count et xp_reward null : rien d'affiché.
    expect(rows[1].textContent).not.toMatch(/intéress|XP/)
  })

  it("event en cours : pastille « En cours » et pas de compte à rebours", () => {
    render(<Events data={{ events: [event("9", "Soirée en cours", "2026-11-20T19:00:00Z", { status: "active" })] }} />)
    const featured = screen.getByTestId("featured-event")
    expect(within(featured).getByText("En cours")).toBeTruthy()
    expect(within(featured).queryByRole("timer")).toBeNull()
    expect(screen.queryByRole("list", { name: "Events suivants" })).toBeNull()
  })

  it("aucun event (état réel actuel) : « Pas d'opération prévue. Repos, soldat. »", () => {
    render(<Events data={{ events: [] }} />)
    expect(screen.getByText("Pas d’opération prévue. Repos, soldat.")).toBeTruthy()
    expect(screen.queryByTestId("featured-event")).toBeNull()
  })

  it("état stale : signale un dernier état connu", () => {
    render(<Events data={{ events: EVENTS, stale: true }} />)
    expect(screen.getByText("Dernier état connu, à vérifier sur Discord")).toBeTruthy()
  })

  it("état null : la section est masquée", () => {
    expect(render(<Events data={null} />).container.innerHTML).toBe("")
  })
})

// ── Frise des grades ──

describe("GradesTimeline", () => {
  it("affiche les 6 grades de la table, triés par seuil, avec le lien « Voir la progression »", () => {
    render(<GradesTimeline grades={GRADES} />)
    expect(screen.getByRole("heading", { name: "Monte en grade" })).toBeTruthy()
    expect(screen.getByText(/Six grades, des quêtes chaque semaine/)).toBeTruthy()
    const items = within(screen.getByRole("list", { name: "Les 6 grades" })).getAllByRole("listitem")
    expect(items.map(li => li.querySelector("b")?.textContent)).toEqual([
      "Recrue Cocktail",
      "Caporal Chipolata",
      "Sergent Merguez",
      "Lieutenant Toulouse",
      "Colonel Saucisson",
      "Général Saucisse",
    ])
    expect(items[0].textContent).toBe("Niveau 1Recrue Cocktaildès ton arrivée")
    expect(items[5].textContent).toContain("on t’érige une statue")
    expect(screen.getByRole("link", { name: "Voir la progression" }).getAttribute("href")).toBe("/progression")
    // Pas de classement sur l'accueil.
    expect(screen.queryByText(/classement/i)).toBeNull()
  })

  it("un grade ajouté depuis l'admin affiche son seuil", () => {
    render(<GradesTimeline grades={[...GRADES, { name: "Maréchal Chorizo", slug: "marechal-chorizo", color: "#fff", level_min: 70 }]} />)
    expect(screen.getByText(/Sept grades/)).toBeTruthy()
    expect(screen.getByText("dès le niveau 70")).toBeTruthy()
  })

  it("grades null ou vides : la section est masquée", () => {
    expect(render(<GradesTimeline grades={null} />).container.innerHTML).toBe("")
    expect(render(<GradesTimeline grades={[]} />).container.innerHTML).toBe("")
  })
})

// ── Démonstration /rang ──

describe("RangDemo", () => {
  it("démonstration /rang marquée « Exemple », grade tiré de la table, chiffres cohérents", () => {
    render(<RangDemo status={HERMES} grades={GRADES} />)
    const demo = screen.getByTestId("rang-demo")
    expect(within(demo).getByText("Exemple")).toBeTruthy()
    expect(within(demo).getByText("commandes-bot")).toBeTruthy()
    expect(within(demo).getByText("/rang")).toBeTruthy()
    expect(within(demo).getByText("BOT")).toBeTruthy()
    // 45 715 XP → niveau 21 (44 100 à 48 400) → Lieutenant Toulouse.
    expect(within(demo).getByText("Chipolata, Lieutenant Toulouse")).toBeTruthy()
    expect(demo.textContent).toContain("Niveau 21, 45 715 XP.")
    expect(demo.textContent).toContain("Encore 2 685 XP avant le niveau 22.")
    // Pas de console sur l'accueil.
    expect(screen.queryByRole("log")).toBeNull()
  })

  it("état normal : statut et chiffres réels d'Hermes", () => {
    render(<RangDemo status={HERMES} grades={GRADES} />)
    expect(screen.getByText("Hermes est en ligne")).toBeTruthy()
    const figures = screen.getByTestId("hermes-figures")
    expect(figures.textContent).toContain("de réponse42 ms")
    expect(figures.textContent).toContain("disponible sur 30 jours99,97 %")
    expect(figures.textContent).toContain("commandes servies12 400")
    expect(screen.getByRole("link", { name: "Ouvrir le tableau de bord d’Hermes" }).getAttribute("href")).toBe("/hermes")
  })

  it("moins de 30 jours de relevés et valeurs absentes : « Depuis le JJ/MM » et « — », jamais de chiffre inventé", () => {
    render(
      <RangDemo
        status={{ ...HERMES, online: false, latency_ms: null, commands_served: null, availability: { percent: null, since: "2026-11-20T08:00:00Z" } }}
        grades={GRADES}
      />,
    )
    expect(screen.getByText("Hermes fait une sieste")).toBeTruthy()
    const figures = screen.getByTestId("hermes-figures")
    expect(figures.textContent).toContain("de réponse—")
    expect(figures.textContent).toContain("en serviceDepuis le 20/11")
    expect(figures.textContent).toContain("commandes servies—")
  })

  it("état stale : statut signalé incertain", () => {
    render(<RangDemo status={{ ...HERMES, stale: true }} grades={GRADES} />)
    expect(screen.getByText("Statut d’Hermes incertain")).toBeTruthy()
    expect(screen.queryByText("Hermes est en ligne")).toBeNull()
  })

  it("état null : démonstration seule, sans statut ni chiffres, et sans nom de grade inventé", () => {
    render(<RangDemo status={null} grades={null} />)
    expect(screen.queryByTestId("hermes-figures")).toBeNull()
    expect(screen.queryByText(/Hermes est en ligne/)).toBeNull()
    // Auteur de la commande et titre de l'embed, sans grade accolé.
    expect(within(screen.getByTestId("rang-demo")).getAllByText("Chipolata")).toHaveLength(2)
    expect(screen.queryByText(/Lieutenant/)).toBeNull()
  })
})

// ── Aperçu galerie ──

describe("GalleryPreview", () => {
  it("affiche au plus 3 moments : capture vers les archives, clip vers son hébergeur", () => {
    const items = [
      moment(1),
      moment(2, { kind: "clip", url: "https://www.youtube.com/watch?v=abc", provider: "youtube", caption: null }),
      moment(3),
      moment(4),
    ]
    render(<GalleryPreview data={{ items }} />)
    const list = screen.getByRole("list", { name: "Moments de la semaine" })
    const links = within(list).getAllByRole("link")
    expect(links).toHaveLength(3)

    expect(links[0].getAttribute("href")).toBe("/galerie")
    expect(links[0].textContent).toBe("CaptureMoment 1Auteur 1")
    expect(links[0].querySelector("img")?.getAttribute("src")).toBe("/media/gallery/1.webp")

    expect(links[1].getAttribute("href")).toBe("https://www.youtube.com/watch?v=abc")
    expect(links[1].getAttribute("target")).toBe("_blank")
    expect(links[1].textContent).toBe("Clip YouTubeSouvenir sans légendeAuteur 2")
    expect(links[1].querySelector("img")).toBeNull()

    expect(screen.getByRole("link", { name: "Toute la galerie" }).getAttribute("href")).toBe("/galerie")
  })

  it("galerie vide (état réel actuel) : invite à poster dans #galerie", () => {
    render(<GalleryPreview data={{ items: [] }} />)
    expect(screen.getByText("Les archives attendent leur premier souvenir.")).toBeTruthy()
    expect(screen.getByText("#galerie")).toBeTruthy()
    expect(screen.queryByRole("list", { name: "Moments de la semaine" })).toBeNull()
    expect(screen.getByRole("link", { name: "Toute la galerie" })).toBeTruthy()
  })

  it("état null : la section est masquée", () => {
    expect(render(<GalleryPreview data={null} />).container.innerHTML).toBe("")
  })
})

// ── Appel final ──

describe("FinalCta", () => {
  it("état normal : présence réelle et bouton vers l'invitation", () => {
    render(<FinalCta live={LIVE} inviteUrl={INVITE} />)
    expect(screen.getByRole("heading", { level: 2, name: "Rejoins les Généraux Saucisses" })).toBeTruthy()
    expect(screen.getByText("312 Généraux en ligne")).toBeTruthy()
    expect(screen.getByRole("link", { name: "Rejoindre le Discord" }).getAttribute("href")).toBe(INVITE)
  })

  it("état stale : heure du dernier relevé", () => {
    render(<FinalCta live={{ ...LIVE, stale: true, updated_at: "2026-11-20T19:55:00Z" }} inviteUrl={INVITE} />)
    expect(screen.getByText("Dernier relevé à 20:55, 312 Généraux en ligne")).toBeTruthy()
  })

  it("état null : pas de pastille, invitation désactivée et expliquée", () => {
    render(<FinalCta live={null} inviteUrl={null} />)
    expect(screen.queryByText(/Généraux en ligne/)).toBeNull()
    const disabled = screen.getByRole("button", { name: "Invitation indisponible pour le moment" })
    expect((disabled as HTMLButtonElement).disabled).toBe(true)
    expect(screen.queryByRole("link", { name: "Rejoindre le Discord" })).toBeNull()
  })
})
