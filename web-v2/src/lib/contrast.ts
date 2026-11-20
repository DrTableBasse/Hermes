// Contraste WCAG 2 entre couleurs hex, et mélanges qui reproduisent `color-mix()` du CSS,
// pour vérifier dans les tests les couples texte/fond réellement rendus.

type Rgb = [number, number, number]

export function hexToRgb(hex: string): Rgb {
  const h = hex.replace("#", "")
  const full = h.length === 3 ? [...h].map(c => c + c).join("") : h
  const n = parseInt(full, 16)
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255]
}

export function rgbToHex([r, g, b]: Rgb): string {
  const c = (v: number) => Math.round(Math.min(255, Math.max(0, v))).toString(16).padStart(2, "0")
  return `#${c(r)}${c(g)}${c(b)}`
}

const toLinear = (v: number) => {
  const s = v / 255
  return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
}
const fromLinear = (l: number) => 255 * (l <= 0.0031308 ? l * 12.92 : 1.055 * l ** (1 / 2.4) - 0.055)

function luminance(hex: string): number {
  const [r, g, b] = hexToRgb(hex).map(toLinear)
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

/** Rapport de contraste WCAG 2 (1 à 21). */
export function contrastRatio(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}

/** `color-mix(in srgb, a p%, b)` ; aussi la composition d'une couleur à opacité p sur le fond b. */
export function mixSrgb(a: string, b: string, p: number): string {
  const [x, y] = [hexToRgb(a), hexToRgb(b)]
  return rgbToHex(x.map((v, i) => v * p + y[i] * (1 - p)) as Rgb)
}

function toOklab(hex: string): Rgb {
  const [r, g, b] = hexToRgb(hex).map(toLinear)
  const l = Math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b)
  const m = Math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b)
  const s = Math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b)
  return [
    0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s,
    1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s,
    0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s,
  ]
}

function fromOklab([L, A, B]: Rgb): string {
  const l = (L + 0.3963377774 * A + 0.2158037573 * B) ** 3
  const m = (L - 0.1055613458 * A - 0.0638541728 * B) ** 3
  const s = (L - 0.0894841775 * A - 1.291485548 * B) ** 3
  return rgbToHex([
    fromLinear(4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s),
    fromLinear(-1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s),
    fromLinear(-0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s),
  ])
}

/** `color-mix(in oklab, a p%, b)`. */
export function mixOklab(a: string, b: string, p: number): string {
  const [x, y] = [toOklab(a), toOklab(b)]
  return fromOklab(x.map((v, i) => v * p + y[i] * (1 - p)) as Rgb)
}
