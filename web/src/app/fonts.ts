import { Bricolage_Grotesque, Instrument_Sans } from "next/font/google"

// Les variables portent le nom de la famille ; globals.css les expose sous --font-display / --font-sans
// (même nom des deux côtés, la déclaration du thème Tailwind se référencerait elle-même).
export const display = Bricolage_Grotesque({
  subsets: ["latin", "latin-ext"],
  weight: ["700", "800"],
  variable: "--font-bricolage",
  display: "swap",
})

export const sans = Instrument_Sans({
  subsets: ["latin", "latin-ext"],
  weight: ["400", "500", "600"],
  variable: "--font-instrument",
  display: "swap",
})

export const fontVariables = `${display.variable} ${sans.variable}`
