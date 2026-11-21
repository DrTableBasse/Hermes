import { cleanup, render, screen, within } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"
import { RankTable } from "@/components/members/rank-table"
import type { RankRow } from "@/lib/members"

const GRADE = { name: "Sergent Merguez", slug: "sergent", color: "#FF8A3D" }

const rows: RankRow[] = [
  { id: "10", rank: 4, name: "Alpha", avatar: null, grade: GRADE, level: 12, score: "5 000 XP" },
  { id: "11", rank: 5, name: "Bravo", avatar: null, grade: null, level: null, score: "4 000 XP" },
]

afterEach(cleanup)

const rowOf = (name: string) => screen.getByRole("link", { name }).closest("tr")!

describe("RankTable", () => {
  it("surligne la ligne du membre connecté (comparaison de chaînes) et la marque « moi »", () => {
    render(<RankTable rows={rows} meId="11" />)
    expect(rowOf("Bravo").getAttribute("data-me")).toBe("true")
    expect(within(rowOf("Bravo")).getByText("moi")).toBeTruthy()
    expect(rowOf("Alpha").getAttribute("data-me")).toBeNull()
  })

  it("un identifiant numérique proche ne surligne rien (snowflakes > 2^53)", () => {
    const big: RankRow[] = [{ ...rows[0], id: "9007199254740993" }]
    render(<RankTable rows={big} meId="9007199254740992" />)
    expect(rowOf("Alpha").getAttribute("data-me")).toBeNull()
  })

  it("surlignage ciblé par ?hl= distinct de « moi »", () => {
    render(<RankTable rows={rows} meId={null} highlightId="10" />)
    expect(rowOf("Alpha").getAttribute("data-highlight")).toBe("true")
    expect(screen.queryByText("moi")).toBeNull()
  })

  it("grade et niveau affichés quand la ligne en porte, lien vers le profil encodé", () => {
    render(<RankTable rows={rows} meId={null} />)
    const alpha = within(rowOf("Alpha"))
    expect(alpha.getByText("Sergent Merguez")).toBeTruthy()
    expect(alpha.getByText(/niv\. 12/)).toBeTruthy()
    expect(screen.getByRole("link", { name: "Alpha" }).getAttribute("href")).toBe("/u/10")
    expect(within(rowOf("Bravo")).queryByText(/niv\./)).toBeNull()
  })

  it("liste vide : message, pas de tableau", () => {
    render(<RankTable rows={[]} meId={null} />)
    expect(screen.queryByRole("table")).toBeNull()
    expect(screen.getByText(/Aucune donnée/)).toBeTruthy()
  })
})
