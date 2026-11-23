"use strict"
/**
 * IP du visiteur pour le limiteur de web-api (constat I1 de la revue de sécurité).
 *
 * Next 16 ne donne pas l'IP de socket à une route : il remplit `x-forwarded-for` avec elle
 * seulement si le client n'a pas envoyé cet en-tête (`??=` dans base-server). `X-Real-IP` et
 * `X-Forwarded-For` restent donc choisis par le client tant qu'aucun reverse proxy ne les écrase,
 * et un client pouvait changer de compteur à chaque requête.
 *
 * Ce module est chargé avant Next (`node --require ./runtime/preload.cjs server.js`). Il intercepte
 * chaque requête HTTP entrante, avant tout code de Next, et pose `x-client-ip` d'autorité :
 * - si `TRUSTED_IP_HEADER` est défini (ex. `cf-connecting-ip` derrière Cloudflare Tunnel) et que
 *   la requête porte cet en-tête avec une IP valide, cette IP ;
 * - sinon l'IP de la socket TCP (celle du pair direct, jamais un en-tête).
 * Un `x-client-ip` envoyé par le client est toujours écrasé. Comme la valeur est posée sur la
 * requête Node elle-même, elle suit aussi les rewrites (`/media/*` relayé à web-api tel quel).
 *
 * Le marqueur `HERMES_CLIENT_IP_PRELOAD` dit au code de Next que l'en-tête est fiable : sans lui
 * (`next dev`, tests), `clientIp()` ne lit rien et web-api compte sous l'IP du conteneur `web`.
 */
const http = require("node:http")

const HEADER = "x-client-ip"
const MARKER = "HERMES_CLIENT_IP_PRELOAD"
// IPv4 ou IPv6 (avec zone éventuelle) : chiffres hexadécimaux, points, deux-points, `%`.
const IP_RE = /^[0-9A-Fa-f.:]{2,39}(%[0-9A-Za-z._-]{1,16})?$/

/** IP normalisée (`::ffff:1.2.3.4` → `1.2.3.4`) ; `null` si la valeur n'a pas la forme d'une IP. */
function normalizeIp(value) {
  if (typeof value !== "string") return null
  let ip = value.trim()
  if (/^::ffff:\d+\.\d+\.\d+\.\d+$/i.test(ip)) ip = ip.slice(7)
  return IP_RE.test(ip) && /[.:]/.test(ip) ? ip : null
}

/** Nom d'en-tête de confiance lu dans l'environnement ; `null` s'il n'est pas défini. */
function trustedHeaderFrom(env) {
  const name = String(env.TRUSTED_IP_HEADER || "").trim().toLowerCase()
  return /^[a-z0-9-]+$/.test(name) ? name : null
}

/**
 * IP à retenir pour une requête : en-tête de confiance s'il est configuré et valide, sinon
 * l'adresse de la socket. Aucun autre en-tête du client n'est jamais lu.
 */
function resolveClientIp(headers, remoteAddress, trustedHeader) {
  if (trustedHeader) {
    const raw = headers[trustedHeader]
    const first = Array.isArray(raw) ? raw[0] : raw
    const ip = normalizeIp(typeof first === "string" ? first.split(",")[0] : undefined)
    if (ip) return ip
  }
  return normalizeIp(remoteAddress)
}

/** Pose (ou retire) `x-client-ip` sur une requête Node entrante. */
function stampRequest(req, trustedHeader) {
  const ip = resolveClientIp(req.headers, req.socket ? req.socket.remoteAddress : undefined, trustedHeader)
  if (ip) req.headers[HEADER] = ip
  else delete req.headers[HEADER]
}

let uninstallCurrent = null

// `upgrade` (WebSocket) contourne `request` : Next relaie ces requêtes vers les rewrites
// (`/media/*`) sans repasser par l'évènement `request` (constat m4).
const STAMPED_EVENTS = new Set(["request", "upgrade"])

/**
 * Intercepte les évènements `request` et `upgrade` de tous les serveurs HTTP du processus ;
 * renvoie l'annulation. `log` reçoit une ligne à l'installation (constat m6 : le démarrage dit
 * si le preload est actif, et selon quelle source).
 */
function install(env = process.env, log = console.info) {
  if (uninstallCurrent) return uninstallCurrent
  const trusted = trustedHeaderFrom(env)
  const proto = http.Server.prototype
  const hadOwn = Object.prototype.hasOwnProperty.call(proto, "emit")
  const original = proto.emit
  proto.emit = function emit(event, ...args) {
    if (STAMPED_EVENTS.has(event) && args[0]) stampRequest(args[0], trusted)
    return original.call(this, event, ...args)
  }
  env[MARKER] = trusted ? `header:${trusted}` : "socket"
  if (typeof log === "function") {
    log(`[client-ip] preload actif : x-client-ip posé depuis ${trusted ? `l'en-tête ${trusted}` : "la socket TCP"}`)
  }
  uninstallCurrent = () => {
    if (hadOwn) proto.emit = original
    else delete proto.emit
    delete env[MARKER]
    uninstallCurrent = null
  }
  return uninstallCurrent
}

module.exports = { HEADER, MARKER, normalizeIp, trustedHeaderFrom, resolveClientIp, stampRequest, install }
