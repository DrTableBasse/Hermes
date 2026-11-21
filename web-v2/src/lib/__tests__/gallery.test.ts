import { SITE_CSP } from "@/lib/security-headers"
import { describe, expect, it } from "vitest"
import { clipEmbedUrl, clipThumbnail, galleryImageSrc, kindLabel, parseClip } from "@/lib/gallery"

const clip = (url: string, provider: string | null) => ({ kind: "clip" as const, url, provider })

describe("lecteurs de clips", () => {
  it("construit l'intégration depuis l'identifiant validé", () => {
    const yt = parseClip(clip("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "youtube"))!
    expect(clipEmbedUrl(yt, "saucisse.land")).toBe("https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ")
    expect(clipThumbnail(yt)).toBe("https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg")

    const tw = parseClip(clip("https://clips.twitch.tv/FunnyClip-abc_1", "twitch"))!
    expect(clipEmbedUrl(tw, "saucisse.land")).toBe("https://clips.twitch.tv/embed?clip=FunnyClip-abc_1&parent=saucisse.land")
    expect(clipThumbnail(tw)).toBeNull()

    const md = parseClip(clip("https://medal.tv/games/minecraft/clips/abc123/statue", "medal"))!
    expect(clipEmbedUrl(md, "x")).toBe("https://medal.tv/games/minecraft/clips/abc123/statue")
    expect(kindLabel(clip("https://medal.tv/games/minecraft/clips/abc123/statue", "medal"))).toBe("Clip Medal")
  })

  it("refuse toute URL hors forme canonique ou fournisseur discordant", () => {
    for (const [url, provider] of [
      ["https://www.youtube.com/watch?v=dQw4w9WgXcQ&autoplay=1", "youtube"],
      ["https://evil.example/watch?v=dQw4w9WgXcQ", "youtube"],
      ["javascript:alert(1)//https://www.youtube.com/watch?v=dQw4w9WgXcQ", "youtube"],
      ["https://clips.twitch.tv/a/b", "twitch"],
      ["https://clips.twitch.tv/abc\"onload=x", "twitch"],
      ["https://medal.tv/../x", "medal"],
      ["https://www.youtube.com/watch?v=dQw4w9WgXcQ", "twitch"],
      ["https://www.youtube.com/watch?v=dQw4w9WgXcQ", null],
      ["https://www.youtube.com/watch?v=dQw4w9WgXcQ", "vimeo"],
    ] as const) {
      expect(parseClip(clip(url, provider)), url).toBeNull()
    }
    expect(kindLabel(clip("https://evil.example", "youtube"))).toBe("Clip")
  })

  it("n'affiche que les images du volume média", () => {
    expect(galleryImageSrc({ kind: "image", url: "/media/gallery/a.png" })).toBe("/media/gallery/a.png")
    expect(galleryImageSrc({ kind: "image", url: "https://evil.example/a.png" })).toBeNull()
    expect(galleryImageSrc({ kind: "image", url: null })).toBeNull()
  })

  it("la CSP autorise les trois lecteurs et rien d'autre", () => {
    // CSP du site : src/lib/security-headers.ts (appliquée par next.config.ts).
    const frameSrc = SITE_CSP.split("; ").find(d => d.startsWith("frame-src "))?.slice(10).split(" ").sort()
    expect(frameSrc).toEqual(["https://clips.twitch.tv", "https://medal.tv", "https://www.youtube-nocookie.com"])
  })
})
