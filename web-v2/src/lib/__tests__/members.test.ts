import { describe, expect, it } from "vitest"
import {
  achievementCategory,
  gradeForLevel,
  isSnowflake,
  isUnknownMember,
  pageOfRank,
  pageWindow,
  parsePage,
  parseTab,
  tierOf,
  toRankRows,
} from "@/lib/members"

const GRADES = [
  { name: "Général", slug: "general", color: "#9B6BFF", level_min: 45 },
  { name: "Recrue", slug: "recrue", color: "#9A97B8", level_min: 1 },
  { name: "Caporal", slug: "caporal", color: "#3BD16F", level_min: 3 },
]

describe("parseTab / parsePage", () => {
  it("onglet inconnu ou absent → vocal", () => {
    expect(parseTab("levels")).toBe("levels")
    expect(parseTab("nimporte")).toBe("voice")
    expect(parseTab(undefined)).toBe("voice")
  })
  it("page invalide → 1", () => {
    expect(parsePage("4")).toBe(4)
    expect(parsePage("0")).toBe(1)
    expect(parsePage("-3")).toBe(1)
    expect(parsePage("abc")).toBe(1)
    expect(parsePage(undefined)).toBe(1)
  })
})

describe("pageWindow / pageOfRank", () => {
  it("garde 1, la dernière et ±2, un trou d'une page est comblé", () => {
    expect(pageWindow(1, 3)).toEqual([1, 2, 3])
    expect(pageWindow(10, 20)).toEqual([1, "gap", 8, 9, 10, 11, 12, "gap", 20])
    expect(pageWindow(4, 9)).toEqual([1, 2, 3, 4, 5, 6, "gap", 9])
    expect(pageWindow(5, 9)).toEqual([1, 2, 3, 4, 5, 6, 7, 8, 9])
  })
  it("page d'un rang", () => {
    expect(pageOfRank(1, 10)).toBe(1)
    expect(pageOfRank(10, 10)).toBe(1)
    expect(pageOfRank(11, 10)).toBe(2)
    expect(pageOfRank(0, 10)).toBe(1)
  })
})

describe("gradeForLevel", () => {
  it("dernier palier atteint, liste non triée acceptée", () => {
    expect(gradeForLevel(2, GRADES)?.slug).toBe("recrue")
    expect(gradeForLevel(3, GRADES)?.slug).toBe("caporal")
    expect(gradeForLevel(44, GRADES)?.slug).toBe("caporal")
    expect(gradeForLevel(99, GRADES)?.slug).toBe("general")
    expect(gradeForLevel(0, GRADES)?.slug).toBe("recrue")
  })
  it("sans liste de grades : null, rien d'inventé", () => {
    expect(gradeForLevel(10, null)).toBeNull()
    expect(gradeForLevel(10, [])).toBeNull()
  })
})

describe("succès", () => {
  it("paliers aux seuils 25 / 50 / 100", () => {
    expect(tierOf(24).label).toBe("Commun")
    expect(tierOf(25).label).toBe("Rare")
    expect(tierOf(50).label).toBe("Épique")
    expect(tierOf(100).label).toBe("Légendaire")
  })
  it("catégorie inconnue → Divers", () => {
    expect(achievementCategory("voice_hours")).toBe("Vocal")
    expect(achievementCategory("???")).toBe("Divers")
  })
})

describe("toRankRows", () => {
  const base = { user_id: "9007199254740993", username: "Kéfir", discord_avatar: null, global_rank: 4 }
  it("niveaux : grade et niveau portés, identifiant en chaîne", () => {
    const [row] = toRankRows("levels", [
      { ...base, current_level: 19, total_xp: 36100, grade: { name: "G", slug: "g", color: "#fff" } },
    ])
    expect(row).toMatchObject({ id: "9007199254740993", rank: 4, level: 19, score: expect.stringMatching(/36.100 XP/) })
    expect(row.grade?.slug).toBe("g")
  })
  it("autres onglets : ni grade ni niveau", () => {
    const [row] = toRankRows("messages", [{ ...base, total_messages: 1500, current_level: 5 }])
    expect(row.grade).toBeNull()
    expect(row.level).toBeNull()
    expect(row.score).toMatch(/1.500 msgs/)
  })
  it("séries : multiplicateur en détail", () => {
    const [row] = toRankRows("streaks", [{ ...base, current_streak: 5, max_streak: 9, xp_multiplier: 1.25 }])
    expect(row.score).toBe("5 j · record 9 j")
    expect(row.detail).toBe("×1.3")
  })
})

describe("erreurs de web-api", () => {
  it("404 et 422 : membre inconnu ; 500 et réseau : non", () => {
    expect(isUnknownMember(new Error("404 /users/1/public"))).toBe(true)
    expect(isUnknownMember(new Error("422 /users/abc/public"))).toBe(true)
    expect(isUnknownMember(new Error("500 /users/1/public"))).toBe(false)
    expect(isUnknownMember(new Error("fetch failed"))).toBe(false)
    expect(isUnknownMember("404 x")).toBe(false)
  })
  it("identifiant Discord", () => {
    expect(isSnowflake("123456789012345678")).toBe(true)
    expect(isSnowflake("..")).toBe(false)
    expect(isSnowflake("12a")).toBe(false)
    expect(isSnowflake("")).toBe(false)
  })
})
