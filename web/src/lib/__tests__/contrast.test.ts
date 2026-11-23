import { readFileSync } from "node:fs"
import { join } from "node:path"
import { describe, expect, it } from "vitest"
import { contrastRatio, mixOklab, mixSrgb } from "@/lib/contrast"

const AA = 4.5
const css = readFileSync(join(__dirname, "../../app/globals.css"), "utf8")
const chipSrc = readFileSync(join(__dirname, "../../components/ui/chip.tsx"), "utf8")

/** Valeur d'un token `--color-x` lue dans globals.css (le test suit le vrai thème). */
function token(name: string): string {
  const m = css.match(new RegExp(`--color-${name}:\\s*(#[0-9A-Fa-f]{6})`))
  if (!m) throw new Error(`token --color-${name} introuvable`)
  return m[1]
}

// Fonds effectifs sous les pastilles : page (bas et haut du dégradé), panneaux, en-tête et embed Discord.
const BACKDROPS = ["#0C0E1A", "#110F24", "#171A2E", "#1A1D33", "#1E2140"]

// Couleurs de grades, de raretés et de jeux (maquette + table site_games), dont les plus sombres.
const CHIP_COLORS = [
  "#9A97B8", "#4D7CFF", "#9B6BFF", "#3FE0F0", "#F2C14E", "#FF8A3D", "#3BD16F",
  "#B3202D", "#7A8A3A", "#0AC8B9", "#3FA9C9", "#F99E1A", "#9D4DFF", "#5DAA3A",
]

describe("contrastRatio", () => {
  it("donne les bornes connues", () => {
    expect(contrastRatio("#000000", "#ffffff")).toBeCloseTo(21)
    expect(contrastRatio("#777777", "#777777")).toBeCloseTo(1)
  })
})

describe("contraste AA des composants", () => {
  it("le texte des pastilles passe 4,5:1 sur leur fond à 14 %, quel que soit le support", () => {
    const share = Number(chipSrc.match(/in_oklab,var\(--c\)_(\d+)%,white/)?.[1]) / 100
    expect(share).toBeGreaterThan(0)
    for (const c of CHIP_COLORS) {
      const text = mixOklab(c, "#ffffff", share)
      for (const backdrop of BACKDROPS) {
        const bg = mixSrgb(c, backdrop, 0.14)
        expect(contrastRatio(text, bg), `${c} sur ${backdrop}`).toBeGreaterThanOrEqual(AA)
      }
    }
  })

  it("le blanc du bouton primary passe 4,5:1 sur tout le dégradé", () => {
    for (const stop of [token("violet-deep"), token("violet-deep-2")]) {
      expect(contrastRatio("#ffffff", stop), stop).toBeGreaterThanOrEqual(AA)
    }
  })

  it("le badge BOT et le bouton Discord passent 4,5:1", () => {
    expect(contrastRatio("#ffffff", token("blue-deep"))).toBeGreaterThanOrEqual(AA)
    expect(contrastRatio("#ffffff", token("discord"))).toBeGreaterThanOrEqual(AA)
  })

  it("la pastille d'exemple et le texte atténué restent lisibles sur le fond le plus clair", () => {
    expect(contrastRatio(token("muted"), "#1E2140")).toBeGreaterThanOrEqual(AA)
  })
})
