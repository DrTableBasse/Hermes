import { describe, expect, it } from "vitest"
import type { AuditEvent } from "@/lib/api/types"
import {
  ACTION_LABELS,
  KIND_LABELS,
  SOURCE_LABELS,
  actionLabel,
  auditQuery,
  detailEntries,
  eventActionLabel,
  filtersFromParams,
  filtersToParams,
} from "@/lib/audit"

const event = (over: Partial<AuditEvent>): AuditEvent => ({
  id: 1,
  occurred_at: "2026-11-23T10:00:00+00:00",
  kind: "voice",
  action: "join",
  source: "discord",
  actor_id: null,
  actor_name: null,
  target_id: null,
  target_name: null,
  channel_id: null,
  channel_name: null,
  success: true,
  details: {},
  ...over,
})

describe("auditQuery", () => {
  it("auditQuery sérialise les filtres non vides et la page", () => {
    expect(auditQuery({ kind: ["command", "sanction"], actor: "Kéfir", failedOnly: true }, 2)).toBe(
      "kind=command%2Csanction&actor=K%C3%A9fir&success=false&page=2",
    )
  })

  it("auditQuery ignore les champs vides", () => {
    expect(auditQuery({ actor: "  " }, 1)).toBe("page=1")
    expect(auditQuery({ kind: [], action: [], q: "", from: "" }, 1)).toBe("page=1")
  })

  it("sans page (export CSV) : filtres seuls", () => {
    expect(auditQuery({ source: ["site"], channelId: "5", from: "2026-11-01", to: "2026-11-23", q: " ban " })).toBe(
      "source=site&channel_id=5&from=2026-11-01&to=2026-11-23&q=ban",
    )
  })
})

describe("filtres dans l’URL de la page", () => {
  it("aller-retour : type, action, auteur, dates, échecs, page", () => {
    const filters = { kind: ["voice"], action: ["join"], actor: "Kéfir", from: "2026-11-01", failedOnly: true }
    const params = filtersToParams(filters, 3)
    expect(params.get("type")).toBe("voice")
    expect(params.get("page")).toBe("3")
    expect(filtersFromParams(params)).toEqual({ filters, page: 3 })
  })

  it("page 1 et filtres vides : URL nue", () => {
    expect(filtersToParams({ actor: " " }, 1).toString()).toBe("")
  })

  it("type ou source inconnus et page invalide ignorés", () => {
    expect(filtersFromParams(new URLSearchParams("type=pirate,message&source=x&page=-2"))).toEqual({
      filters: { kind: ["message"] },
      page: 1,
    })
  })
})

describe("libellés", () => {
  it("couvrent tous les kinds, sources et actions de la liste fermée", () => {
    const kinds = [
      "command", "sanction", "message", "voice", "member", "member_role", "role", "channel", "thread",
      "invite", "emoji", "server", "permission", "setting", "game", "site_access", "content",
    ]
    for (const k of kinds) expect(KIND_LABELS[k], k).toBeTruthy()
    expect(KIND_LABELS.command).toBe("Commande")
    expect(KIND_LABELS.site_access).toBe("Accès au site")
    expect(KIND_LABELS.emoji).toBe("Émoji")
    expect(SOURCE_LABELS).toEqual({ site: "Site", hermes: "Hermes", discord: "Discord" })
    const actions = [
      "edit", "delete", "bulk_delete", "join", "leave", "move", "server_mute", "server_deafen", "self_mute",
      "self_deafen", "stream_start", "stream_stop", "nickname", "add", "remove", "create", "update",
      "kick", "ban", "unban", "timeout", "untimeout", "warn", "clear", "message_delete", "message_bulk_delete",
    ]
    for (const a of actions) expect(ACTION_LABELS[a], a).toBeTruthy()
    expect(ACTION_LABELS.edit).toBe("modifié")
    expect(ACTION_LABELS.join).toBe("arrivée")
    // Jamais écrite par le bot : absente de la liste fermée (M6).
    expect(ACTION_LABELS.avatar).toBeUndefined()
  })

  it("action inconnue ou commande : affichée telle quelle", () => {
    expect(actionLabel("/fortnite")).toBe("/fortnite")
    expect(actionLabel("inconnue")).toBe("inconnue")
  })

  it("vocal : micro et casque selon details.active (R8)", () => {
    expect(eventActionLabel(event({ action: "self_mute", details: { active: true } }))).toBe("micro coupé")
    expect(eventActionLabel(event({ action: "self_mute", details: { active: false } }))).toBe("micro réactivé")
    expect(eventActionLabel(event({ action: "self_deafen", details: { active: true } }))).toBe("casque coupé")
    expect(eventActionLabel(event({ action: "server_mute", details: { active: true } }))).toBe(
      "micro coupé par la modération",
    )
    expect(eventActionLabel(event({ action: "server_deafen", details: { active: false } }))).toBe(
      "casque réactivé par la modération",
    )
    expect(eventActionLabel(event({ action: "stream_start", details: { active: true } }))).toBe("partage d’écran lancé")
    expect(eventActionLabel(event({ action: "stream_stop", details: { active: false } }))).toBe("partage d’écran arrêté")
  })
})

describe("detailEntries", () => {
  it("raison, durée et options de commande en paires lisibles ; identifiants techniques masqués", () => {
    const entries = detailEntries(
      event({
        kind: "command",
        action: "/blague",
        details: { reason: "spam", duration_minutes: 10, options: { theme: "chat", n: 2 }, discord_audit_id: 9 },
      }),
    )
    expect(entries).toEqual([
      { label: "Raison", value: "spam" },
      { label: "Durée (minutes)", value: "10" },
      { label: "Option « theme »", value: "chat" },
      { label: "Option « n »", value: "2" },
    ])
  })

  it("message modifié : avant / après", () => {
    const entries = detailEntries(
      event({
        kind: "message",
        action: "edit",
        details: {
          message_id: 7,
          avant: { content: "salut", attachments: [], embeds: 0 },
          après: { content: "salut à tous", attachments: ["a.png"], embeds: 1 },
        },
      }),
    )
    expect(entries).toEqual([
      { label: "Avant", value: "salut" },
      { label: "Après", value: "salut à tous · pièces jointes : a.png · 1 embed" },
    ])
  })

  it("changement de rôle ou de salon : champ avant → après", () => {
    const entries = detailEntries(
      event({
        kind: "role",
        action: "update",
        details: { changes: { name: { avant: "Modo", après: "Modération" }, hoist: { avant: false, après: true } }, reason: null },
      }),
    )
    expect(entries).toEqual([
      { label: "name", value: "Modo → Modération" },
      { label: "hoist", value: "non → oui" },
    ])
  })

  it("ligne vide : aucun détail", () => {
    expect(detailEntries(event({ details: {} }))).toEqual([])
  })
})
