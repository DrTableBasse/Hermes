import { cleanup, render, screen, within } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"
import { GamesStrip } from "@/components/home/games-strip"
import { Hero, gradeForLevel } from "@/components/home/hero"
import { LiveBarracks, buildCurvePaths } from "@/components/home/live-barracks"
import type { CurvePoint, Game, Grade, LiveFeed, LiveState } from "@/lib/api/types"
import { gameOfTheWeek } from "@/lib/games"

afterEach(cleanup)

// ── Données d'exemple, de la forme renvoyée par web-api ──

const NOW = new Date("2026-11-20T20:10:00Z") // 21:10 à Paris

const GRADES: Grade[] = [
  { name: "Caporal Chipolata", slug: "caporal-chipolata", color: "#4D7CFF", level_min: 3 },
  { name: "Recrue Cocktail", slug: "recrue-cocktail", color: "#9A97B8", level_min: 1 },
  { name: "Sergent Merguez", slug: "sergent-merguez", color: "#9B6BFF", level_min: 8 },
  { name: "Lieutenant Toulouse", slug: "lieutenant-toulouse", color: "#3FE0F0", level_min: 15 },
  { name: "Colonel Saucisson", slug: "colonel-saucisson", color: "#F2C14E", level_min: 25 },
  { name: "Général Saucisse", slug: "general-saucisse", color: "#FF8A3D", level_min: 45 },
]

function curve(values: Array<number | null>): CurvePoint[] {
  return values.map((online, i) => ({
    hour: new Date(Date.UTC(2026, 10, 19, 21 + i)).toISOString(),
    online,
  }))
}

// 24 heures : un trou de deux heures (indices 5-6) ; pic à l'indice 23 = 20:00 UTC = 21 h à Paris.
const CURVE = curve([40, 38, 30, 22, 18, null, null, 12, 15, 20, 26, 30, 34, 38, 41, 45, 50, 55, 60, 70, 80, 90, 95, 120])

const LIVE: LiveState = {
  members: 1240,
  online: 312,
  in_voice: 37,
  voice_avatars: [
    "https://cdn.discordapp.com/avatars/1/a.png",
    "https://cdn.discordapp.com/avatars/2/b.png",
    "https://cdn.discordapp.com/avatars/3/c.png",
    "https://cdn.discordapp.com/avatars/4/d.png",
    "https://cdn.discordapp.com/avatars/5/e.png",
    "https://cdn.discordapp.com/avatars/6/f.png",
  ],
  game_players: { dbd: 48 },
  stale: false,
  updated_at: "2026-11-20T20:09:30Z",
  messages_today: 4812,
  curve_24h: CURVE,
}

const STALE: LiveState = {
  ...LIVE,
  stale: true,
  voice_avatars: [],
  game_players: {},
  updated_at: "2026-11-20T19:55:00Z", // 20:55 à Paris
}

const FEED: LiveFeed = {
  items: [
    { type: "level_up", user_id: "1", username: "Kéfir", avatar: null, label: "Niveau 12 atteint !", at: "2026-11-20T20:08:00Z" },
    { type: "achievement", user_id: "2", username: "Merguez_Royale", avatar: null, label: "🌭 Général du dimanche", at: "2026-11-20T20:04:00Z" },
  ],
}

const game = (key: string, name: string, extra: Partial<Game> = {}): Game => ({
  key,
  name,
  color: "#ED4245",
  image: null,
  players: null,
  forum_url: null,
  ...extra,
})

const GAMES: Game[] = [
  game("war-dogs", "War Dogs"),
  game("dbd", "Dead by Daylight", { players: 48, forum_url: "https://discord.com/channels/1/2" }),
  game("lol", "League of Legends", { players: 1 }),
  game("warframe", "Warframe", { players: 0 }),
  game("overwatch", "Overwatch", { image: "/media/overwatch.webp" }),
  game("fortnite", "Fortnite"),
  game("minecraft", "Minecraft"),
]

const INVITE = "https://discord.gg/saucisseland"

// ── Hero ──

describe("Hero", () => {
  it("affiche titre, accroche, boutons, grades et compteurs réels", () => {
    render(<Hero live={LIVE} grades={GRADES} gamesCount={7} inviteUrl={INVITE} />)
    expect(screen.getByRole("heading", { level: 1, name: "Bienvenue à SaucisseLand" })).toBeTruthy()
    expect(screen.getByText(/^Garde-à-vous, recrue\./)).toBeTruthy()
    expect(screen.getByRole("link", { name: "Rejoindre le Discord" }).getAttribute("href")).toBe(INVITE)
    expect(screen.getByRole("link", { name: "Voir la progression" }).getAttribute("href")).toBe("/progression")
    expect(screen.getByText("Le QG est ouvert, 312 Généraux en ligne")).toBeTruthy()

    // Les 6 grades, triés par seuil.
    const chips = within(screen.getByRole("list", { name: "Les grades de la caserne" })).getAllByRole("listitem")
    expect(chips.map(c => c.textContent)).toEqual(GRADES.toSorted((a, b) => a.level_min - b.level_min).map(g => g.name))

    const stats = screen.getByTestId("hero-stats")
    // formatNumber sépare les milliers par une espace fine insécable (U+202F).
    expect(stats.textContent).toContain("1 240membres")
    expect(stats.textContent).toContain("312en ligne")
    expect(stats.textContent).toContain("7jeux")
  })

  it("compose la scène : vocal « Cantine des Généraux », #général avec Hermes, carte profil marquée Exemple", () => {
    render(<Hero live={LIVE} grades={GRADES} gamesCount={7} inviteUrl={INVITE} />)
    const scene = screen.getByTestId("hero-scene")
    expect(within(scene).getByText("Cantine des Généraux, vocal")).toBeTruthy()
    expect(within(scene).getByText("général")).toBeTruthy()
    expect(within(scene).getByText("BOT")).toBeTruthy()
    // Les grades de la scène viennent de la table, pas d'un texte en dur.
    expect(within(scene).getByText(/Andouillette passe Caporal Chipolata \(niveau 5\)/)).toBeTruthy()
    expect(within(scene).getByText("Exemple")).toBeTruthy()
    expect(within(scene).getByText(/Prochain grade : Lieutenant Toulouse/)).toBeTruthy()
    expect(within(scene).getByText("Série de 9 jours, cuisson parfaite")).toBeTruthy()
    expect(screen.getByTestId("hero-horizon")).toBeTruthy()
  })

  it("état stale : signale l'heure du dernier relevé", () => {
    render(<Hero live={STALE} grades={GRADES} gamesCount={7} inviteUrl={INVITE} />)
    expect(screen.getByText("Dernier relevé à 20:55, 312 Généraux en ligne")).toBeTruthy()
    expect(screen.queryByText(/Le QG est ouvert/)).toBeNull()
  })

  it("état null : compteurs « — », pas de pastille, pas de grades, invitation désactivée et expliquée", () => {
    render(<Hero live={null} grades={null} gamesCount={null} inviteUrl={null} />)
    expect(screen.queryByText(/Généraux en ligne/)).toBeNull()
    expect(screen.queryByRole("list", { name: "Les grades de la caserne" })).toBeNull()
    const stats = screen.getByTestId("hero-stats")
    expect(stats.textContent).toBe("—membres—en ligne")
    const disabled = screen.getByRole("button", { name: "Invitation indisponible pour le moment" })
    expect((disabled as HTMLButtonElement).disabled).toBe(true)
    expect(screen.queryByRole("link", { name: "Rejoindre le Discord" })).toBeNull()
    // Sans grades, la scène n'invente pas de nom de grade.
    expect(screen.getByText(/Andouillette passe \(niveau 5\)/)).toBeTruthy()
  })
})

describe("gradeForLevel", () => {
  it("prend le dernier seuil atteint, quel que soit l'ordre reçu", () => {
    expect(gradeForLevel(GRADES, 1)?.slug).toBe("recrue-cocktail")
    expect(gradeForLevel(GRADES, 7)?.slug).toBe("caporal-chipolata")
    expect(gradeForLevel(GRADES, 45)?.slug).toBe("general-saucisse")
    expect(gradeForLevel(GRADES, 0)).toBeNull()
    expect(gradeForLevel(null, 10)).toBeNull()
  })
})

// ── Caserne en direct ──

describe("LiveBarracks", () => {
  it("état normal : 4 cartes réelles, courbe, avatars en vocal et fil d'activité", () => {
    render(<LiveBarracks live={LIVE} feed={FEED} now={NOW} />)
    expect(screen.getByRole("heading", { name: "La caserne en direct" })).toBeTruthy()
    expect(screen.getByText("En direct, chiffres fournis par Hermes")).toBeTruthy()
    for (const [label, value] of [
      ["Membres", "1 240"],
      ["En ligne maintenant", "312"],
      ["En vocal", "37"],
      ["Messages aujourd’hui", "4 812"],
    ]) {
      expect(screen.getByText(label).nextElementSibling?.textContent).toBe(value)
    }
    expect(screen.getByRole("img", { name: "Courbe des membres en ligne sur 24 heures" })).toBeTruthy()
    expect(screen.getByText("Pic à 21 h sur les dernières 24 heures")).toBeTruthy()
    // 5 avatars au plus.
    expect(screen.getByTestId("voice-avatars").children).toHaveLength(5)

    const ticker = screen.getByRole("list", { name: "Activité récente" })
    expect(ticker.textContent).toContain("Il y a 2 min")
    expect(ticker.textContent).toContain("Kéfir : Niveau 12 atteint !")
    expect(ticker.textContent).toContain("Merguez_Royale débloque « 🌭 Général du dimanche »")
  })

  it("état stale : mention « Dernier relevé à HH:MM » à la place du direct", () => {
    render(<LiveBarracks live={STALE} feed={{ items: [] }} now={NOW} />)
    expect(screen.getByText(/^Dernier relevé à 20:55/)).toBeTruthy()
    expect(screen.queryByText("En direct, chiffres fournis par Hermes")).toBeNull()
    expect(screen.queryByTestId("voice-avatars")).toBeNull()
    expect(screen.queryByRole("list", { name: "Activité récente" })).toBeNull()
  })

  it("état null : la section est masquée", () => {
    const { container } = render(<LiveBarracks live={null} feed={FEED} now={NOW} />)
    expect(container.innerHTML).toBe("")
  })

  it("sans aucun relevé sur 24 h, n'affiche pas de courbe inventée", () => {
    render(<LiveBarracks live={{ ...LIVE, curve_24h: curve(Array(24).fill(null)) }} feed={null} now={NOW} />)
    expect(screen.queryByTestId("online-curve")).toBeNull()
    expect(screen.getByText("Pas encore de relevé sur 24 h.")).toBeTruthy()
    expect(screen.queryByText(/^Pic à/)).toBeNull()
  })
})

describe("buildCurvePaths", () => {
  it("coupe la courbe sur les heures sans relevé au lieu de les inventer", () => {
    const paths = buildCurvePaths(CURVE)
    expect(paths.lines).toHaveLength(2)
    expect(paths.areas).toHaveLength(2)
    // 5 points avant le trou, 17 après.
    expect(paths.lines[0].split("L")).toHaveLength(5)
    expect(paths.lines[1].split("L")).toHaveLength(17)
  })

  it("dessine en point une heure isolée", () => {
    const paths = buildCurvePaths(curve([null, 10, null, 12, 14]))
    expect(paths.dots).toHaveLength(1)
    expect(paths.lines).toHaveLength(1)
  })
})

// ── Jeux ──

describe("GamesStrip", () => {
  it("met en vedette le jeu de la semaine et fait défiler toute la liste de l'API", () => {
    const { container } = render(<GamesStrip games={GAMES} now={NOW} inviteUrl={INVITE} />)
    const section = container.querySelector("section#jeux")
    expect(section).not.toBeNull()
    expect(screen.getByText(/^Sept jeux, un seul Discord\./)).toBeTruthy()

    const featured = screen.getByTestId("featured-game")
    expect(within(featured).getByText("Jeu de la semaine")).toBeTruthy()
    expect(within(featured).getByRole("heading", { level: 3 }).textContent).toBe(gameOfTheWeek(GAMES, NOW).name)

    const marquee = screen.getByRole("region", { name: "Tous nos jeux" })
    // Contenu doublé par le bandeau : 7 cartes visibles + 7 copies masquées.
    expect(within(marquee).getAllByRole("heading", { level: 4 })).toHaveLength(7)
    expect(marquee.querySelectorAll("h4")).toHaveLength(14)
  })

  it("affiche le nombre de joueurs seulement s'il est connu, et relie au forum ou à l'invitation", () => {
    render(<GamesStrip games={GAMES} now={NOW} inviteUrl={INVITE} />)
    const marquee = screen.getByRole("region", { name: "Tous nos jeux" })
    const card = (name: string) => within(marquee).getByRole("heading", { level: 4, name }).closest("article")!

    expect(card("Dead by Daylight").textContent).toContain("48 Généraux")
    expect(within(card("Dead by Daylight")).getByRole("link", { name: "Trouver des joueurs" }).getAttribute("href")).toBe(
      "https://discord.com/channels/1/2",
    )
    expect(card("League of Legends").textContent).toContain("1 Général")
    expect(card("Warframe").textContent).toContain("Place libre")
    expect(card("War Dogs").textContent).not.toMatch(/Généra/)
    expect(within(card("War Dogs")).getByRole("link", { name: "Trouver des joueurs" }).getAttribute("href")).toBe(INVITE)
  })

  it("image absente : emplacement stylé à la couleur du jeu ; image fournie : elle est affichée", () => {
    render(<GamesStrip games={GAMES} now={NOW} inviteUrl={INVITE} />)
    const marquee = screen.getByRole("region", { name: "Tous nos jeux" })
    const visual = (name: string) =>
      within(marquee).getByRole("heading", { level: 4, name }).closest("article")!.querySelector("[data-game-visual]")!

    expect(visual("War Dogs").getAttribute("data-game-visual")).toBe("placeholder")
    expect(visual("War Dogs").textContent).toBe("Visuel à venir")
    expect((visual("War Dogs") as HTMLElement).style.getPropertyValue("--g1")).toBe("#ED4245")
    expect(visual("Overwatch").getAttribute("data-game-visual")).toBe("image")
    expect(visual("Overwatch").querySelector("img")?.getAttribute("src")).toBe("/media/overwatch.webp")
  })

  it("sans invitation ni forum, pas de bouton « Trouver des joueurs » mort", () => {
    render(<GamesStrip games={[game("war-dogs", "War Dogs")]} now={NOW} inviteUrl={null} />)
    expect(screen.queryByRole("link", { name: "Trouver des joueurs" })).toBeNull()
    expect(screen.getByText(/^Un jeu, un seul Discord\./)).toBeTruthy()
  })

  it("liste null ou vide : la section est masquée", () => {
    expect(render(<GamesStrip games={null} now={NOW} inviteUrl={INVITE} />).container.innerHTML).toBe("")
    expect(render(<GamesStrip games={[]} now={NOW} inviteUrl={INVITE} />).container.innerHTML).toBe("")
  })
})
