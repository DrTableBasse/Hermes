import { describe, expect, it } from "vitest"
import { canEdit, canWrite, excerpt, safeImageSrc, tagColor } from "@/lib/articles"

const me = (over: Partial<{ user_id: string; is_admin: boolean; is_redacteur: boolean }> = {}) => ({
  user_id: "100",
  is_admin: false,
  is_redacteur: false,
  ...over,
})

describe("safeImageSrc", () => {
  it("garde un chemin du volume média", () => {
    expect(safeImageSrc("/media/abc-123.png")).toBe("/media/abc-123.png")
  })

  it("ramène une ancienne URL absolue vers web-api au chemin local", () => {
    expect(safeImageSrc("https://hermes.example/api/proxy/media/abc.webp")).toBe("/media/abc.webp")
    expect(safeImageSrc("http://localhost:8000/media/abc.jpg")).toBe("/media/abc.jpg")
  })

  it("accepte le CDN Discord en https, rien d'autre", () => {
    expect(safeImageSrc("https://cdn.discordapp.com/attachments/1/2/x.png")).toBe(
      "https://cdn.discordapp.com/attachments/1/2/x.png",
    )
    expect(safeImageSrc("http://cdn.discordapp.com/x.png")).toBeNull()
    expect(safeImageSrc("https://evil.example/x.png")).toBeNull()
  })

  it("refuse les schémas dangereux, les chemins hors média et le vide", () => {
    expect(safeImageSrc("javascript:alert(1)")).toBeNull()
    expect(safeImageSrc("data:image/svg+xml,<svg/>")).toBeNull()
    expect(safeImageSrc("/media/../secret.png")).toBeNull()
    expect(safeImageSrc("/autre/chemin.png")).toBeNull()
    expect(safeImageSrc("//evil.example/media/x.png")).toBeNull()
    expect(safeImageSrc("   ")).toBeNull()
    expect(safeImageSrc(null)).toBeNull()
    expect(safeImageSrc(undefined)).toBeNull()
  })
})

describe("excerpt", () => {
  it("retire les marques Markdown et compacte les espaces", () => {
    expect(excerpt("# Titre\n\n**Gras** et `code`")).toBe("Titre Gras et code")
  })

  it("coupe à la longueur demandée", () => {
    expect(excerpt("a".repeat(500), 160)).toHaveLength(160)
  })
})

describe("droits", () => {
  it("canWrite : rédacteur ou administrateur, pas un simple membre ni une absence de session", () => {
    expect(canWrite(me({ is_redacteur: true }))).toBe(true)
    expect(canWrite(me({ is_admin: true }))).toBe(true)
    expect(canWrite(me())).toBe(false)
    expect(canWrite(null)).toBe(false)
  })

  it("canEdit : l'auteur ou un administrateur ; un autre rédacteur ne modifie pas", () => {
    expect(canEdit(me({ user_id: "42" }), { author_id: "42" })).toBe(true)
    expect(canEdit(me({ is_admin: true }), { author_id: "42" })).toBe(true)
    expect(canEdit(me({ is_redacteur: true }), { author_id: "42" })).toBe(false)
    expect(canEdit(null, { author_id: "42" })).toBe(false)
  })
})

describe("tagColor", () => {
  it("n'injecte qu'une couleur hexadécimale à six chiffres", () => {
    expect(tagColor("#3b82f6")).toBe("#3b82f6")
    expect(tagColor("red; background:url(x)")).toBe("#9A97B8")
    expect(tagColor(null)).toBe("#9A97B8")
  })
})
