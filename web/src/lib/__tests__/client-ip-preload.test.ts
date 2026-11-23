// @vitest-environment node
import { createRequire } from "node:module"
import http from "node:http"
import type { AddressInfo } from "node:net"
import { afterEach, describe, expect, it } from "vitest"
import { CLIENT_IP_MARKER } from "@/lib/api/forward"

interface ClientIpModule {
  HEADER: string
  MARKER: string
  normalizeIp(value: unknown): string | null
  trustedHeaderFrom(env: Record<string, string | undefined>): string | null
  resolveClientIp(
    headers: Record<string, string | string[] | undefined>,
    remoteAddress: string | undefined,
    trustedHeader: string | null,
  ): string | null
  install(env?: Record<string, string | undefined>, log?: ((line: string) => void) | null): () => void
}

const mod = createRequire(import.meta.url)("../../../runtime/client-ip.cjs") as ClientIpModule

let uninstall: (() => void) | null = null
afterEach(() => {
  uninstall?.()
  uninstall = null
})

/** Serveur réel : renvoie le `x-client-ip` vu par le gestionnaire, après interception. */
async function seenIp(env: Record<string, string | undefined>, headers: Record<string, string>) {
  uninstall = mod.install(env, null)
  const server = http.createServer((req, res) => res.end(String(req.headers["x-client-ip"] ?? "")))
  await new Promise<void>(resolve => server.listen(0, "127.0.0.1", resolve))
  const { port } = server.address() as AddressInfo
  try {
    return await new Promise<string>((resolve, reject) => {
      http
        .get({ host: "127.0.0.1", port, path: "/", headers }, res => {
          let body = ""
          res.on("data", c => (body += c))
          res.on("end", () => resolve(body))
        })
        .on("error", reject)
    })
  } finally {
    await new Promise(resolve => server.close(resolve))
  }
}

describe("runtime/client-ip.cjs (constat I1)", () => {
  it("le marqueur est celui que lit clientIp()", () => {
    expect(mod.MARKER).toBe(CLIENT_IP_MARKER)
    expect(mod.HEADER).toBe("x-client-ip")
  })

  it("écrase x-client-ip, X-Real-IP et X-Forwarded-For n'y changent rien : IP de socket", async () => {
    const env: Record<string, string | undefined> = {}
    const ip = await seenIp(env, {
      "x-client-ip": "6.6.6.6",
      "x-real-ip": "7.7.7.7",
      "x-forwarded-for": "8.8.8.8, 9.9.9.9",
    })
    expect(ip).toBe("127.0.0.1")
    expect(env[CLIENT_IP_MARKER]).toBe("socket")
  })

  it("TRUSTED_IP_HEADER défini : IP du proxy de confiance (première entrée)", async () => {
    const env: Record<string, string | undefined> = { TRUSTED_IP_HEADER: "CF-Connecting-IP" }
    const ip = await seenIp(env, { "cf-connecting-ip": "203.0.113.7", "x-client-ip": "6.6.6.6" })
    expect(ip).toBe("203.0.113.7")
    expect(env[CLIENT_IP_MARKER]).toBe("header:cf-connecting-ip")
  })

  it("TRUSTED_IP_HEADER absent de la requête ou invalide : repli sur la socket", async () => {
    const env = { TRUSTED_IP_HEADER: "cf-connecting-ip" }
    expect(await seenIp({ ...env }, { "x-client-ip": "6.6.6.6" })).toBe("127.0.0.1")
    uninstall?.()
    expect(await seenIp({ ...env }, { "cf-connecting-ip": "pas-une-ip" })).toBe("127.0.0.1")
  })

  it("requête Upgrade (WebSocket) : x-client-ip aussi écrasé (constat m4)", async () => {
    const env: Record<string, string | undefined> = {}
    uninstall = mod.install(env, null)
    const server = http.createServer()
    server.on("upgrade", (req, socket) => {
      const seen = String(req.headers["x-client-ip"] ?? "")
      socket.end(`HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nX-Seen: ${seen}\r\n\r\n`)
    })
    await new Promise<void>(resolve => server.listen(0, "127.0.0.1", resolve))
    const { port } = server.address() as AddressInfo
    try {
      const seen = await new Promise<string>((resolve, reject) => {
        http
          .request({
            host: "127.0.0.1",
            port,
            path: "/media/x",
            headers: { connection: "Upgrade", upgrade: "websocket", "x-client-ip": "6.6.6.6" },
          })
          .on("upgrade", (res, socket) => {
            socket.destroy()
            resolve(String(res.headers["x-seen"]))
          })
          .on("error", reject)
          .end()
      })
      expect(seen).toBe("127.0.0.1")
    } finally {
      await new Promise(resolve => server.close(resolve))
    }
  })

  it("installation : une ligne de log dit la source de l'IP (constat m6)", () => {
    const lines: string[] = []
    mod.install({ TRUSTED_IP_HEADER: "cf-connecting-ip" }, line => lines.push(line))()
    mod.install({}, line => lines.push(line))()
    expect(lines).toHaveLength(2)
    expect(lines[0]).toContain("cf-connecting-ip")
    expect(lines[1]).toContain("socket")
  })

  it("annulation : l'interception disparaît avec le marqueur", async () => {
    const env: Record<string, string | undefined> = {}
    mod.install(env, null)()
    expect(env[CLIENT_IP_MARKER]).toBeUndefined()
    const server = http.createServer()
    expect(Object.prototype.hasOwnProperty.call(http.Server.prototype, "emit")).toBe(false)
    server.close()
  })

  it("normalise les IP et refuse ce qui n'en a pas la forme", () => {
    expect(mod.normalizeIp("::ffff:192.0.2.1")).toBe("192.0.2.1")
    expect(mod.normalizeIp(" 2001:db8::1 ")).toBe("2001:db8::1")
    expect(mod.normalizeIp("fe80::1%eth0")).toBe("fe80::1%eth0")
    expect(mod.normalizeIp("abc")).toBeNull()
    expect(mod.normalizeIp("1.2.3.4; DROP")).toBeNull()
    expect(mod.normalizeIp(undefined)).toBeNull()
    expect(mod.trustedHeaderFrom({ TRUSTED_IP_HEADER: " " })).toBeNull()
    expect(mod.trustedHeaderFrom({ TRUSTED_IP_HEADER: "bad header" })).toBeNull()
  })

  it("resolveClientIp : l'en-tête de confiance n'est lu que s'il est configuré", () => {
    const headers = { "cf-connecting-ip": "203.0.113.7" }
    expect(mod.resolveClientIp(headers, "10.0.0.2", null)).toBe("10.0.0.2")
    expect(mod.resolveClientIp(headers, "10.0.0.2", "cf-connecting-ip")).toBe("203.0.113.7")
    expect(mod.resolveClientIp({}, undefined, null)).toBeNull()
  })
})
