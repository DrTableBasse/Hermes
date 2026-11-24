import { cleanup, render, screen, within } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"
import { AchievementsShowcase, rarityOf, shareText } from "@/components/progression/achievements-showcase"
import { CharacterSheet } from "@/components/progression/character-sheet"
import { GradeLadder } from "@/components/progression/grade-ladder"
import { LeaderboardTable } from "@/components/progression/leaderboard-table"
import { WeeklyQuests } from "@/components/progression/weekly-quests"
import type { AchievementCatalog, Grade, LevelEntry, Quest } from "@/lib/api/types"

afterEach(cleanup)

// ── Données de la forme renvoyée par web-api ──

const GRADES: Grade[] = [
  { name: "Caporal Chipolata", slug: "caporal-chipolata", color: "#4D7CFF", level_min: 5 },
  { name: "Recrue Cocktail", slug: "recrue-cocktail", color: "#9A97B8", level_min: 1 },
  { name: "Sergent Merguez", slug: "sergent-merguez", color: "#9B6BFF", level_min: 10 },
  { name: "Lieutenant Toulouse", slug: "lieutenant-toulouse", color: "#3FE0F0", level_min: 20 },
  { name: "Colonel Saucisson", slug: "colonel-saucisson", color: "#F2C14E", level_min: 30 },
  { name: "Général Saucisse", slug: "general-saucisse", color: "#FF8A3D", level_min: 50 },
]

const quest = (id: number, extra: Partial<Quest> = {}): Quest => ({
  id,
  title: `Quête ${id}`,
  description: null,
  quest_type: "messages",
  target_value: 30,
  xp_reward: 150,
  icon: null,
  current_progress: 0,
  status: "active",
  week_start: "2026-11-16",
  week_end: "2026-11-22",
  is_active: true,
  ...extra,
})

const entry = (rank: number, id: string, name: string, level: number, xp: number, grade: Grade): LevelEntry => ({
  user_id: id,
  username: name,
  discord_avatar: null,
  current_level: level,
  total_xp: xp,
  global_rank: rank,
  grade: { name: grade.name, slug: grade.slug, color: grade.color },
})

// ── Fiche d'exemple ──

describe("CharacterSheet", () => {
  it("affiche l'étiquette « Exemple » et des chiffres cohérents avec la formule d'XP", () => {
    render(<CharacterSheet grades={GRADES} />)
    const sheet = screen.getByTestId("character-sheet")
    expect(within(sheet).getByText("Exemple")).toBeTruthy()
    expect(within(sheet).getByText(/toi, dans 3 semaines/i)).toBeTruthy()
    // 21 300 XP : niveau 14 (19 600), niveau 15 à 22 500.
    expect(sheet.textContent).toContain("Niveau 14")
    expect(sheet.textContent).toMatch(/1\s200 XP avant le niveau 15/)
    expect(within(sheet).getByText("Sergent Merguez")).toBeTruthy()
    expect(sheet.textContent).toContain("Lieutenant Toulouse au niveau 20")
  })

  it("reste un exemple lisible sans grades (API indisponible)", () => {
    render(<CharacterSheet grades={null} />)
    const sheet = screen.getByTestId("character-sheet")
    expect(within(sheet).getByText("Exemple")).toBeTruthy()
    expect(sheet.textContent).toContain("Niveau 14")
    expect(sheet.textContent).not.toContain("Sergent")
  })
})

// ── Échelle des grades ──

describe("GradeLadder", () => {
  it("trie les grades et donne niveaux et XP requis pour chacun", () => {
    render(<GradeLadder grades={GRADES} />)
    const rungs = screen.getAllByRole("listitem")
    expect(rungs.map(r => r.getAttribute("data-grade"))).toEqual([
      "recrue-cocktail",
      "caporal-chipolata",
      "sergent-merguez",
      "lieutenant-toulouse",
      "colonel-saucisson",
      "general-saucisse",
    ])
    expect(rungs[0].textContent).toContain("niveaux 1 à 4")
    expect(rungs[2].textContent).toContain("niveaux 10 à 19")
    expect(rungs[2].textContent).toMatch(/10\s000 XP/)
    expect(rungs[5].textContent).toContain("niveau 50 et plus")
    expect(rungs[5].textContent).toMatch(/250\s000 XP/)
  })

  it("se masque sans grades", () => {
    const { container: a } = render(<GradeLadder grades={null} />)
    expect(a.innerHTML).toBe("")
    cleanup()
    const { container: b } = render(<GradeLadder grades={[]} />)
    expect(b.innerHTML).toBe("")
  })
})

// ── Quêtes de la semaine ──

describe("WeeklyQuests", () => {
  it("affiche les vraies quêtes avec leur avancement", () => {
    render(
      <WeeklyQuests
        signedIn
        quests={[
          quest(1, { title: "Dire bonjour à 3 nouveaux", target_value: 3, current_progress: 3, status: "completed", xp_reward: 80 }),
          quest(2, { title: "30 min en vocal", current_progress: 18 }),
          quest(3, { title: "Bumper le serveur", status: "claimed", target_value: 1, current_progress: 1 }),
        ]}
      />,
    )
    const items = screen.getAllByRole("listitem")
    expect(items).toHaveLength(3)
    expect(items[0].textContent).toContain("+80 XP")
    expect(items[0].textContent).toContain("Terminée")
    expect(items[1].textContent).toContain("18 sur 30")
    expect(items[2].textContent).toContain("Récompense ajoutée à ton XP")
    expect(screen.getAllByRole("progressbar")[1].getAttribute("aria-valuenow")).toBe("60")
  })

  it("invite à se connecter sans session", () => {
    render(<WeeklyQuests signedIn={false} quests={null} />)
    expect(screen.getByText(/Connecte-toi/)).toBeTruthy()
    expect(screen.queryAllByRole("listitem")).toHaveLength(0)
  })

  it("signale une API indisponible et une semaine sans quête", () => {
    render(<WeeklyQuests signedIn quests={null} />)
    expect(screen.getByText(/indisponibles/)).toBeTruthy()
    cleanup()
    render(<WeeklyQuests signedIn quests={[]} />)
    expect(screen.getByText(/Pas de quête cette semaine/)).toBeTruthy()
  })
})

// ── Vitrine de succès ──

describe("AchievementsShowcase", () => {
  // 200 membres actifs : 1 → 0,5 %, 6 → 3 %, 30 → 15 %, 120 → 60 %.
  const catalogOf = (rows: Array<[number, string, number]>, members_total = 200): AchievementCatalog => ({
    achievements: rows.map(([id, name, unlocked_count]) => ({
      id,
      name,
      description: `Description de ${name}`,
      icon: "🏆",
      points: 10,
      condition_type: "messages",
      unlocked_count,
    })),
    members_total,
  })
  const CATALOG = catalogOf([
    [1, "Premier message", 120],
    [2, "Bavard", 30],
    [3, "Moulin à paroles", 6],
    [4, "Légende du chat", 1],
    [5, "Nocturne", 0],
  ])

  it("classe la rareté selon la part réelle des membres", () => {
    expect(rarityOf(0).label).toBe("Légendaire")
    expect(rarityOf(0.0099).label).toBe("Légendaire")
    expect(rarityOf(0.01).label).toBe("Épique")
    expect(rarityOf(0.049).label).toBe("Épique")
    expect(rarityOf(0.05).label).toBe("Rare")
    expect(rarityOf(0.199).label).toBe("Rare")
    expect(rarityOf(0.2).label).toBe("Commun")
  })

  it("formule la part des membres sans jamais afficher « 0 % »", () => {
    expect(shareText(0, 0)).toBe("encore jamais débloqué")
    expect(shareText(1, 0.0005)).toBe("débloqué par moins de 0,1 % des membres")
    expect(shareText(1, 0.005)).toBe("débloqué par 0,5 % des membres")
    expect(shareText(6, 0.03)).toBe("débloqué par 3 % des membres")
    expect(shareText(120, 0.604)).toBe("débloqué par 60 % des membres")
  })

  it("groupe les vrais succès du plus rare au plus commun, avec leur pourcentage", () => {
    render(<AchievementsShowcase catalog={CATALOG} unlockedIds={null} />)
    const groups = screen.getAllByTestId("rarity-group")
    expect(groups.map(g => g.getAttribute("data-rarity"))).toEqual(["legendaire", "epique", "rare", "commun"])
    expect(within(groups[0]).getByText("Nocturne")).toBeTruthy()
    expect(within(groups[0]).getByText("Légende du chat")).toBeTruthy()
    expect(groups[1].textContent).toContain("Moulin à paroles")
    expect(groups[1].textContent).toContain("débloqué par 3 % des membres")
    expect(within(groups[3]).getByText("Premier message")).toBeTruthy()
    expect(screen.getByText(/part des 200 membres/)).toBeTruthy()
    // Aucun succès inventé : les noms provisoires de la maquette n'apparaissent pas s'ils manquent en base.
    expect(screen.queryByText("Général du dimanche")).toBeNull()
    expect(screen.queryByText("Moutarde au nez")).toBeNull()
    expect(screen.queryByText("Chipolata nocturne")).toBeNull()
    expect(screen.queryByText(/débloqués/)).toBeNull()
  })

  it("affiche un succès de la maquette dès qu'il existe en base", () => {
    render(<AchievementsShowcase catalog={catalogOf([[9, "Général du dimanche", 1]])} unlockedIds={null} />)
    expect(screen.getByText("Général du dimanche")).toBeTruthy()
  })

  it("marque les succès débloqués du membre connecté", () => {
    render(<AchievementsShowcase catalog={CATALOG} unlockedIds={new Set([1])} />)
    expect(screen.getByText(/1 sur 5 débloqués/)).toBeTruthy()
    expect(screen.getByText("Bavard").closest("[data-locked]")?.getAttribute("data-locked")).toBe("true")
    expect(screen.getByText("Premier message").closest("[data-locked]")?.getAttribute("data-locked")).toBe("false")
  })

  it("se masque sans catalogue, catalogue vide ou sans membre (API indisponible)", () => {
    for (const catalog of [null, catalogOf([]), catalogOf([[1, "Bavard", 0]], 0)]) {
      const { container } = render(<AchievementsShowcase catalog={catalog} unlockedIds={null} />)
      expect(container.innerHTML).toBe("")
      cleanup()
    }
  })
})

// ── Classement par niveau ──

describe("LeaderboardTable", () => {
  it("affiche le classement réel avec grade et lien vers le profil", () => {
    render(
      <LeaderboardTable
        entries={[
          entry(1, "111", "Merguez_Royale", 90, 812_000, GRADES[5]),
          entry(2, "222", "Kéfir", 19, 36_100, GRADES[2]),
        ]}
      />,
    )
    const rows = screen.getAllByRole("row").slice(1)
    expect(rows).toHaveLength(2)
    expect(within(rows[0]).getByRole("link", { name: "Merguez_Royale" }).getAttribute("href")).toBe("/u/111")
    expect(within(rows[0]).getByText("Général Saucisse")).toBeTruthy()
    expect(rows[0].textContent).toContain("niv. 90")
    expect(rows[0].textContent).toMatch(/812\s000 XP/)
    expect(within(rows[1]).getByText("Sergent Merguez")).toBeTruthy()
  })

  it("affiche l'avatar Discord en direct, réduit à 64 px, sans initiale de secours", () => {
    const withAvatar = {
      ...entry(1, "111", "Merguez_Royale", 90, 812_000, GRADES[5]),
      discord_avatar: "https://cdn.discordapp.com/avatars/111/abc.png?size=1024",
    }
    render(<LeaderboardTable entries={[withAvatar]} />)
    const row = screen.getAllByRole("row")[1]
    const img = row.querySelector("img")
    expect(img?.getAttribute("src")).toBe("https://cdn.discordapp.com/avatars/111/abc.png?size=64")
    expect(within(row).queryByText("M")).toBeNull()
  })

  it("signale un classement indisponible ou vide", () => {
    render(<LeaderboardTable entries={null} />)
    expect(screen.getByText(/Classement indisponible/)).toBeTruthy()
    cleanup()
    render(<LeaderboardTable entries={[]} />)
    expect(screen.getByText(/Personne au classement/)).toBeTruthy()
  })
})
